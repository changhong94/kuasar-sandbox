import pathlib,subprocess,os,json,time,sqlite3,fcntl,hashlib,traceback
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2');T=R/'tools';D=R/'results';P='/srv/fork2/bin/python-sdk'
lock=open('/run/skyrl-threeway-benchmark.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);os.environ['FORK2_FULL_LOCK_HELD']='1';os.environ.update(NO_PROXY='*',no_proxy='*')
def empty():
 deadline=time.monotonic()+120
 while True:
  with sqlite3.connect('file:/srv/fork2/data/base/node-ctl.db?mode=ro',uri=True)as d:ids=[r[0] for r in d.execute('select id from sandboxes')]
  if not ids:return
  if time.monotonic()>=deadline:raise TimeoutError('Sandbox deletion did not settle: '+repr(ids))
  time.sleep(.05)
records=json.loads((R/'status.json').read_text()).get('stages',[]) if (R/'status.json').exists() else []
def save(phase,**kw):
 p=R/'status.json';q=p.with_suffix('.tmp');q.write_text(json.dumps(dict(phase=phase,updated_ns=time.time_ns(),stages=records,**kw),indent=2));q.replace(p)
def stage(name,*args):
 if any(r['name']==name and r['exit_code']==0 for r in records):return
 empty();save(name,complete=False);start=time.time_ns()
 log=R/'logs'/f'{name}.log'
 if log.exists():log.rename(log.with_name(log.name+'.attempt-'+str(start)))
 with log.open('w')as f:r=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT)
 records.append(dict(name=name,exit_code=r.returncode,start_ns=start,end_ns=time.time_ns()));assert r.returncode==0,(name,r.returncode);empty();save(name+'-finished',complete=False)
def sdk(name,script,*args):stage(name,P,'-u',str(T/script),*args)
try:
 empty();cfg=json.load(open('/srv/fork2/conductor.json'));p=next(p for p in cfg['units']['runner_pools']if p.get('prepared_vm'));assert p['size']==64 and p['prepare_concurrency']==8
 (R/'provenance.json').write_text(json.dumps({'started_ns':time.time_ns(),'products':['fork2'],'binary_sha256':{p:hashlib.sha256((pathlib.Path('/srv/fork2/bin')/p).read_bytes()).hexdigest()for p in ['node-ctl','sandbox-ctl','node-vm-runner','cloud-hypervisor']},'images':{l:json.load(open('/srv/fork2/data/registry/'+l+'.json'))['manifest']for l in ['python','node','ruby']}},indent=2))
 stage('pool-preparation','python3',str(T/'pool50.py'),'current','50')
 sdk('discover-backings','discover_backings.py')
 stage('three-language-startup','python3',str(T/'startup_all.py'))
 sdk('pause-restore','pause_restore.py','--count','50','--output',str(D/'pause-restore.json'))
 sdk('resources','full_resources.py')
 sdk('storage','storage.py','--count','3','--output',str(D/'storage.json'))
 sdk('memory','memory.py','fork2')
 sdk('live-fork','live_fork.py')
 for gap in [0,10,25,50,100]:sdk('burst-'+str(gap),'burst_latest.py',str(D/'paced'/str(gap)),str(gap))
 sdk('lifecycle','lifecycle.py')
 sdk('snapshot-local','snapshot_modes.py','local')
 stage('snapshot-remote','python3',str(T/'resume_remote.py'))
 stage('idle-audit','python3',str(T/'audit_idle_resources.py'))
 stage('cleanup','python3',str(T/'cleanup.py'))
 save('complete',complete=True);print('FULL_BENCH_COMPLETE',flush=True)
except BaseException as e:
 save('failed-needs-review',complete=False,error=repr(e));traceback.print_exc();raise
