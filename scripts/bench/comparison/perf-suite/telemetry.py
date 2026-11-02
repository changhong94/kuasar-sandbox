"""Read-only Linux telemetry. Never reads process environments or emits secrets.

PSS, cgroup memory and host memory are independent views, NOT additive.
Process CPU/I/O deltas miss exited processes; cgroup counters are also retained.
"""
import json
import os
from pathlib import Path
import subprocess
import time

def fields(text):
    result = {}
    for line in text.splitlines():
        k, _, v = line.partition(':') if ':' in line else line.partition(' ')
        try: result[k] = int(v.split()[0])
        except (ValueError, IndexError): pass
    return result

def read(path):
    try: return Path(path).read_text()
    except OSError: return ''

def inventory():
    rows = {}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit(): continue
        try:
            raw = (p/'stat').read_text().rsplit(')', 1)[1].split()
            rows[int(p.name)] = dict(ppid=int(raw[1]), start_ticks=int(raw[19]),
                cpu_seconds=(int(raw[11])+int(raw[12]))/os.sysconf('SC_CLK_TCK'),
                minor_faults=int(raw[7]),major_faults=int(raw[9]),
                comm=(p/'comm').read_text().strip(),
                cmd=(p/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace'),
                cgroup=(p/'cgroup').read_text().strip().split('::')[-1])
        except (OSError, IndexError, ValueError): continue
    return rows

def descendants(rows, roots):
    selected=set(roots)
    while True:
        extra={pid for pid,r in rows.items() if r['ppid'] in selected}-selected
        if not extra: return selected
        selected |= extra

def cube_containers():
    q=subprocess.run(['docker','ps','--format','{{.Names}}'],capture_output=True,text=True,timeout=10)
    names=[n for n in q.stdout.splitlines() if n.startswith('cube-')]
    if not names: return []
    q=subprocess.run(['docker','inspect','--format','{{.State.Pid}}',*names],capture_output=True,text=True,timeout=10)
    return [int(n) for n in q.stdout.split() if n.isdigit()]

def roots_for(rows, product, docker_roots=()):
    roots=[]
    for pid,r in rows.items():
        cg=r['cgroup']
        if product=='kuasar' and ('/kuasar-comparison-' in cg): roots.append(pid)
        if product=='cube' and ('/cube-sandbox-' in cg or cg.startswith('/cube_sandbox/')): roots.append(pid)
        if product=='agentenv' and '/agentenv-comparison.service' in cg: roots.append(pid)
    if product=='cube': roots+=list(docker_roots)
    return roots

def capture(product, sids=(), docker_roots=()):
    started=time.monotonic()
    table=inventory()
    owned=descendants(table,[p for p,r in table.items() if any(sid and sid in r['cmd'] for sid in sids)])
    platform=descendants(table,roots_for(table,product,docker_roots))
    selected=owned|platform
    rows=[]; groups={}
    for pid in sorted(selected):
        r=table[pid];p=Path('/proc')/str(pid)
        try:
            mem=fields((p/'smaps_rollup').read_text())
            status=fields((p/'status').read_text())
            row={k:r[k] for k in ('ppid','comm','start_ticks','cpu_seconds','cgroup','minor_faults','major_faults')}
            row.update(pid=pid,scope='owned' if pid in owned else 'platform_or_existing',memory_kib=mem,
                threads=status.get('Threads'),fd_count=len(list((p/'fd').iterdir())),
                voluntary_context_switches=status.get('voluntary_ctxt_switches'),
                involuntary_context_switches=status.get('nonvoluntary_ctxt_switches'),io=fields(read(p/'io')))
            rows.append(row)
            cg=r['cgroup'];base=Path('/sys/fs/cgroup')/cg.lstrip('/')
            if cg not in groups:
                groups[cg]={n:read(base/n) for n in ('memory.current','memory.peak','memory.stat','memory.events','cpu.stat','io.stat','cpu.pressure','memory.pressure','io.pressure')}
        except OSError: continue
    selected_cgroups=set(groups)
    top=[cg for cg in selected_cgroups if not any(cg.startswith(parent.rstrip('/')+'/') for parent in selected_cgroups if parent!=cg)]
    memory_current=sum(int(groups[cg]['memory.current'].strip() or 0) for cg in top)
    return dict(time=time.time(),monotonic=time.monotonic(),product=product,owned_sids=list(sids),
        processes=rows,cgroups=groups,nonoverlapping_cgroup_memory_bytes=memory_current,
        host_memory_kib=fields(read('/proc/meminfo')),host_cpu=read('/proc/stat').splitlines()[0],
        host_vmstat=fields(read('/proc/vmstat')),diskstats=read('/proc/diskstats'),
        host_pressure={n:read('/proc/pressure/'+n) for n in ('cpu','memory','io')},
        totals={scope:{k:sum(r['memory_kib'].get(k,0) for r in rows if scope=='all' or r['scope']==scope)
                 for k in ('Pss','Pss_Anon','Pss_File','Pss_Shmem','Rss','Swap')}
                for scope in ('all','owned','platform_or_existing')},
        capture_ms=(time.monotonic()-started)*1000,
        scope='Product process set plus owned descendants. Shared cgroups may include unrelated clients; PSS and cgroup values must not be added.')

def storage(paths, extents=False):
    rows=[];seen=set();device_groups={}
    for root in paths:
        root=Path(root).resolve()
        if not root.is_dir():
            rows.append(dict(path=str(root),error='missing'));continue
        logical=allocated=count=0
        for directory,dirs,names in os.walk(root,followlinks=False):
            dirs[:]=[d for d in dirs if not Path(directory,d).is_symlink()]
            for name in names:
                p=Path(directory,name)
                try:
                    s=p.lstat()
                    if not p.is_file() or p.is_symlink() or (s.st_dev,s.st_ino) in seen:continue
                    seen.add((s.st_dev,s.st_ino));logical+=s.st_size;allocated+=s.st_blocks*512;count+=1
                except OSError:continue
        stat=os.statvfs(root)
        rows.append(dict(path=str(root),logical_bytes=logical,allocated_bytes=allocated,files=count,
                         filesystem_used_bytes=(stat.f_blocks-stat.f_bfree)*stat.f_frsize))
        device_groups.setdefault(root.stat().st_dev,[]).append(str(root))
    result=dict(time=time.time(),directories=rows,allocated_bytes=sum(r.get('allocated_bytes',0) for r in rows),
                scope='Allocated file blocks count reflink/shared extents more than once; use extent union for unique physical file data. Filesystem used is whole-filesystem context only.')
    if extents:
        # Reuse the existing tested FIEMAP helper, one filesystem per union.
        from extent_accounting import scan
        result['extent_unions']=[]
        for paths in device_groups.values():
            try: result['extent_unions'].append(dict(paths=paths,**scan(paths)))
            except Exception as e:result['extent_unions'].append(dict(paths=paths,error=str(e)))
    return result
