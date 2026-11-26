import json,pathlib,sqlite3,subprocess,time,os
R=pathlib.Path('/home/hong/src/research/sevenway-current-20261126/fork2')
db=sqlite3.connect('file:/home/hong/src/research/fork2-control-persistent/node-ctl.db?mode=ro',uri=True)
assigned=db.execute('select count(*) from sandboxes').fetchone()[0]
assert assigned==0,assigned
units=[json.loads(row[0])['unit'] for row in db.execute('select ownership from run_pool_ownership')]
assert all(x.startswith('fork2-runner@') for x in units)
units+=['fork2-conductor.service','fork2-store.service','fork2-proxy.service','fork2-switch.service']
seen=set();rows=[]
for unit in units:
 cg=subprocess.check_output(['systemctl','show',unit,'-p','ControlGroup','--value'],text=True).strip()
 if not cg:continue
 base=pathlib.Path('/sys/fs/cgroup'+cg)
 for f in base.rglob('cgroup.procs'):
  for pid in f.read_text().split():
   if pid in seen:continue
   seen.add(pid);p=pathlib.Path('/proc')/pid
   try:
    mem={}
    for line in (p/'smaps_rollup').read_text().splitlines():
     a=line.split()
     if a[0] in ('Pss:','Pss_Anon:','Pss_File:','Private_Dirty:','Private_Clean:'):mem[a[0][:-1]]=int(a[1])
    rows.append(dict(pid=int(pid),unit=unit,comm=(p/'comm').read_text().strip(),fd_count=len(list((p/'fd').iterdir())),memory_kib=mem))
   except (FileNotFoundError,ProcessLookupError):continue
out=dict(unix=time.time(),assigned=assigned,owned_runner_units=len(units)-4,scope='All descendants of dedicated fork2 service cgroups; no other product processes',processes=rows,total_fd_count=sum(x['fd_count'] for x in rows),pss_kib=sum(x['memory_kib'].get('Pss',0) for x in rows),limitations='Single idle snapshot; does not establish absence of FD accumulation across generations')
path=R/'results'/('idle-resources-'+str(int(out['unix']))+'.json');path.write_text(json.dumps(out,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='processes'}))
