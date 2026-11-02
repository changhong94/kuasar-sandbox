"""One product per process. Operates only on instances created by this worker."""
import argparse
import concurrent.futures
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import sys
import threading
import time
import traceback
import uuid

from telemetry import capture, storage, fields, read, inventory, cube_containers
import workloads

p=argparse.ArgumentParser()
p.add_argument('--workspace',required=True)
p.add_argument('--config',required=True)
p.add_argument('--product',choices=['kuasar','cube','agentenv'],required=True)
p.add_argument('--output',required=True)
p.add_argument('--case',choices=['runtime','memory','density','storage','pressure','recovery','resume'],required=True)
p.add_argument('--count',type=int,default=1)
p.add_argument('--requests',type=int,default=6)
p.add_argument('--rate',type=float,default=0)
p.add_argument('--limit',type=int,default=2)
p.add_argument('--sample',action='store_true')
p.add_argument('--extents',action='store_true')
p.add_argument('--different',action='store_true')
p.add_argument('--entropy',choices=['low','high'],default='high')
a=p.parse_args()
if not (1<=a.count<=32 and 1<=a.limit<=32 and 1<=a.requests<=10000):p.error('bounded counts required')
W=Path(a.workspace);cfg=json.loads(Path(a.config).read_text())
c=json.loads(Path('/home/hong/src/.deployment/agentenv-setup/access.json' if a.product=='agentenv' else cfg['products'][a.product]['access']).read_text())
for key in ('E2B_DOMAIN','E2B_API_URL','E2B_SANDBOX_URL','http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY'):os.environ.pop(key,None)
os.environ.update(E2B_API_KEY=c['api_key'],SSL_CERT_FILE=c.get('ca_file','/etc/ssl/certs/ca-certificates.crt'),NO_PROXY='*',no_proxy='*')
if a.product=='agentenv':os.environ.update(E2B_API_URL=c['api_url'],E2B_SANDBOX_URL=c['api_url'])
else:
    os.environ['E2B_DOMAIN']=c['domain']
    if a.product=='cube':os.environ['E2B_API_URL']=c['api_url']
from e2b import Sandbox

out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
template=json.loads((W/f'fixture-{a.product}-openssl-selfsigned-cert.json').read_text())['template']
marker=' # perf-suite-'+uuid.uuid4().hex
owned={};mutex=threading.RLock();done=threading.Event();phase='before';monitor=None
docker_roots=cube_containers() if a.product=='cube' else []
paths=cfg['products'][a.product].get('live_extent_paths',[]) if a.product!='agentenv' else ['/var/lib/agentenv-comparison']
result=dict(product=a.product,case=a.case,args=vars(a),template=template,prefetch='off' if a.product=='kuasar' else 'not_applicable',
    started=time.time(),requests=[],stages={},cleanup=[],workload_sha256={k:hashlib.sha256(getattr(workloads,k).encode()).hexdigest() for k in ('CPU','MEMORY','IO','STORAGE','PRESSURE')},
    qualification='functional pilot unless isolated host and repetitions independently verified',
    baseline_vm_pids=[pid for pid,r in inventory().items() if r['comm'] in ('firecracker','cloud-hypervisor')])

def interrupted(signum,frame):
    raise KeyboardInterrupt('worker interrupted; cleaning owned instances')
signal.signal(signal.SIGTERM,interrupted)

def save():
    with mutex:
        tmp=out/'result.json.tmp';tmp.write_text(json.dumps(result,indent=2));tmp.replace(out/'result.json')

def hosts(hostname=None):
    if a.product!='kuasar':return
    with open('/run/comparison-hosts.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);f=Path('/etc/hosts')
        if hostname:
            with f.open('a') as h:h.write('\n127.0.0.2 '+hostname+marker+'\n')
        else:f.write_text(''.join(l for l in f.read_text().splitlines(True) if marker not in l))

def guard():
    if fields(read('/proc/meminfo')).get('MemAvailable',0)<4*1024*1024:raise RuntimeError('Stopped: available host memory below 4 GiB')
    v=os.statvfs(out)
    if v.f_bavail*v.f_frsize<5*1024**3:raise RuntimeError('Stopped: available output disk below 5 GiB')

def snap(name,disk=False):
    global phase
    phase=name
    with mutex:sids=list(owned)
    row=capture(a.product,sids,docker_roots)
    if disk:row['storage']=storage(paths,a.extents)
    result['stages'][name]=row;save()

def sample():
    with (out/'telemetry.jsonl').open('w') as f:
        while not done.is_set():
            with mutex:sids=list(owned)
            try:
                r=capture(a.product,sids,docker_roots);r['phase']=phase;f.write(json.dumps(r)+'\n');f.flush()
            except Exception as e:f.write(json.dumps(dict(time=time.time(),error=repr(e)))+'\n');f.flush()
            done.wait(1)

def command(s,cmd,timeout=90):
    # Match the already validated Harbor exec transport: explicit task cwd,
    # start once in background, then wait without dispatching a second command.
    t=time.perf_counter();handle=s.commands.run(cmd,user='root',cwd='/app',background=True,timeout=timeout);q=handle.wait()
    return dict(client_ms=(time.perf_counter()-t)*1000,exit_code=q.exit_code,stdout=q.stdout,stderr=q.stderr)

def python(s,code,name,tail=''):
    path='/tmp/perf-'+name+'.py';s.files.write(path,code,user='root')
    return command(s,'python3 '+shlex.quote(path)+' '+tail,180)

def create(index,scheduled=None):
    guard();row=dict(index=index,scheduled_monotonic=scheduled,begin_monotonic=time.monotonic());t=time.perf_counter()
    with mutex:result['requests'].append(row)
    kw={}
    if a.product=='kuasar':kw['metadata']={'kuasar-sandbox.restore':'{"prefetch":"off"}','kuasar-sandbox.resource':json.dumps({'capacity':{'cpu':1,'memory':'2048MiB'},'allocatable':{'cpu':1,'memory':'2048MiB'}})}
    try:
        s=Sandbox.create(template,timeout=1200,**kw)
        with mutex:owned[s.sandbox_id]=s
        row.update(sid=s.sandbox_id,api_return_ms=(time.perf_counter()-t)*1000);save();hosts(s.get_host(49983))
        deadline=time.monotonic()+45;last=''
        while time.monotonic()<deadline:
            try:
                q=command(s,'printf PERF_READY',5)
                if q['stdout']=='PERF_READY':break
            except Exception as e:last=repr(e)
            time.sleep(.1)
        else:raise TimeoutError('Readiness: '+last)
        row['ready_ms']=(time.perf_counter()-t)*1000
        if scheduled is not None:row['scheduled_to_ready_ms']=(time.monotonic()-scheduled)*1000
        row['success']=True;save();return s,row
    except Exception as e:
        row.update(success=False,error=repr(e),elapsed_ms=(time.perf_counter()-t)*1000);save();raise

def delete(s):
    t=time.perf_counter()
    try:
        s.kill()
        with mutex:owned.pop(s.sandbox_id,None)
        result['cleanup'].append(dict(sid=s.sandbox_id,sdk_kill_ms=(time.perf_counter()-t)*1000,success=True))
    except Exception as e:
        result['cleanup'].append(dict(sid=s.sandbox_id,success=False,error=repr(e)))
    save()

def pressure_one(i,scheduled=None):
    s=None
    try:
        s,row=create(i,scheduled);q=command(s,workloads.PRESSURE)
        expected=hashlib.sha256(b'paired-pressure-v1'*65536).hexdigest()
        if q['stdout'].strip()!=expected:raise RuntimeError('Pressure workload hash mismatch')
        row['workload']=q;row['work_complete_monotonic']=time.monotonic()
    except Exception as e:
        if s is not None:row.update(success=False,error=repr(e))
    finally:
        if s is not None:delete(s)

try:
    save();snap('before',a.case=='storage')
    if a.sample:
        monitor=threading.Thread(target=sample,daemon=True);monitor.start()
    phase='running'
    if a.case in ('pressure','recovery'):
        # Open-loop scheduling never silently waits for a client slot. Locally
        # rejected requests remain in the denominator; this is not a server 503.
        rejected=0;t0=time.monotonic();pending=set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.limit) as pool:
            for i in range(a.requests):
                guard()
                scheduled=t0+i/a.rate if a.rate>0 else None
                if scheduled is not None:time.sleep(max(0,scheduled-time.monotonic()))
                pending={f for f in pending if not f.done()}
                if len(pending)>=a.limit:
                    if a.rate>0:
                        result['requests'].append(dict(index=i,scheduled_monotonic=scheduled,success=False,error='client_inflight_limit',client_rejected=True));rejected+=1;save();continue
                    concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
                pending.add(pool.submit(pressure_one,i,scheduled))
        result['load_seconds']=time.monotonic()-t0;result['client_rejected']=rejected
        if a.case=='recovery':
            snap('after_burst')
            previous=0
            for offset in (1,5,15):
                time.sleep(offset-previous);previous=offset
                s,row=create(10000+offset);row['recovery_offset_seconds']=offset;delete(s);snap('recovery_'+str(offset))
    else:
        live=[]
        for i in range(a.count):
            s,row=create(i);live.append(s)
            row['platform']=command(s,'uname -r; nproc; grep MemTotal /proc/meminfo; python3 --version; openssl version')
            if a.case=='runtime':
                row['short_commands']=[command(s,'true') for _ in range(12)]
                row['cpu']=python(s,workloads.CPU,'cpu');row['io']=python(s,workloads.IO,'io')
                expected=hashlib.sha256();block=hashlib.shake_256(b'perf-cpu-v1').digest(1024*1024)
                for _ in range(256):expected.update(block)
                assert json.loads(row['cpu']['stdout'])['sha256']==expected.hexdigest()
                row['file_transfer']=[]
                for size in (1024,1024*1024):
                    payload=hashlib.shake_256(b'perf-transfer-v1').digest(size)
                    t=time.perf_counter();s.files.write('/tmp/perf-transfer.bin',payload,user='root');upload=(time.perf_counter()-t)*1000
                    t=time.perf_counter();returned=bytes(s.files.read('/tmp/perf-transfer.bin',format='bytes',user='root'));download=(time.perf_counter()-t)*1000
                    assert returned==payload
                    row['file_transfer'].append(dict(bytes=size,upload_ms=upload,download_ms=download,sha256=hashlib.sha256(payload).hexdigest()))
            if a.case=='memory':
                phase='memory_allocate_write_unmap';row['memory']=python(s,workloads.MEMORY,'memory')
            if a.case=='storage':
                seed=str(i if a.different else 0)
                code=workloads.STORAGE.replace("('low','high')",repr((a.entropy,)))
                row['files']=python(s,code,'storage',shlex.quote('different' if a.different else 'same')+' '+seed)
            snap('live_'+str(i+1),a.case=='storage')
        if a.case=='storage':
            digests=[tuple(f['sha256'] for f in json.loads(r['files']['stdout'])['files']) for r in result['requests']]
            assert len(set(digests))==(a.count if a.different else 1),'Content identity does not match scenario'
            result['content_identity_verified']=True
        if a.case in ('resume','storage'):
            for s,row in zip(live,result['requests']):
                token=uuid.uuid4().hex;s.files.write('/tmp/perf-resume-token',token,user='root')
                t=time.perf_counter();s.beta_pause();row['pause_ms']=(time.perf_counter()-t)*1000
                snap('paused_'+str(row['index']),a.case=='storage')
                time.sleep(1);t=time.perf_counter()
                resumed=Sandbox.connect(s.sandbox_id,timeout=1200)
                with mutex:owned[s.sandbox_id]=resumed
                deadline=time.monotonic()+60
                while True:
                    try:
                        q=command(resumed,'cat /tmp/perf-resume-token',5)
                        if q['stdout']==token:break
                    except Exception:
                        if time.monotonic()>deadline:raise
                    if time.monotonic()>deadline:raise TimeoutError('Resume token check')
                    time.sleep(.1)
                row['resume_to_verified_ms']=(time.perf_counter()-t)*1000
                if a.case=='storage':
                    expected=json.loads(row['files']['stdout'])['files']
                    row['restored_files']=command(resumed,'sha256sum /tmp/perf-storage/*.bin')
                    assert all(x['sha256'] in row['restored_files']['stdout'] for x in expected)
                save()
        if a.case=='density':time.sleep(3);snap('held')
    result['completed']=True
except BaseException:
    result['completed']=False;result['error']=traceback.format_exc()
finally:
    phase='cleanup'
    for s in list(owned.values()):delete(s)
    snap('after_delete',a.case=='storage')
    time.sleep(3);snap('after_settle',a.case=='storage')
    done.set()
    if monitor:monitor.join(timeout=15)
    hosts();result.update(finished=time.time(),owned_remaining=list(owned));save()
    print(json.dumps(dict(product=a.product,case=a.case,completed=result.get('completed'),output=str(out),owned_remaining=list(owned))),flush=True)
if not result.get('completed') or owned:sys.exit(1)
