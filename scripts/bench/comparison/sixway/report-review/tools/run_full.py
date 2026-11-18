from pathlib import Path
import os,sys,subprocess as sp,json,time,fcntl,shutil,hashlib
B=Path('/home/hong/src/research/report-review-113');T=B/'tools';R=B/'results';sys.path.insert(0,str(T));import runner as b
lock=open('/run/skyrl-threeway-benchmark.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
os.environ['FIVEWAY_LOCK_HELD']='1'
R.mkdir(exist_ok=True)
(R/'scope.json').write_text(json.dumps(dict(products=b.prods,initial_ready_reserves={'kuasar-fork':64,'kuasar-mlink':64},mlink_total_slot_capacity=320,timing_rounds=5,pressure_requests_per_round=8,pressure_concurrency=2,storage_rounds=3,storage_instances=2,storage_write_mib=32,growth_instances=50,array_mib_per_instance=20,array_modes=['default','100','random'],python_startup_samples_per_product=50,python_startup_source=str(R/'matrix'),startup_metric='client create invocation to random Python print receipt',fork='113 sandbox_fork_staging with Manifest integration',fork_persistent_pause_resume='tested',fork_application_writes='qcow2 ext4 persistent overlay'),indent=2))
(R/'tool-hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in T.glob('*.py')},indent=2))
def run(name,cmd):
 (R/'progress.json').write_text(json.dumps(dict(phase=name,started_at=time.time())))
 print('START',name,flush=True)
 with (R/(name+'.log')).open('w') as f:r=sp.run(list(map(str,cmd)),stdout=f,stderr=sp.STDOUT)
 if r.returncode:raise RuntimeError((name,r.returncode))
 print('END',name,flush=True)
def validate(folder,n):
 rows=[]
 for p in folder.glob('*.json'):
  d=json.loads(p.read_text())
  if isinstance(d,dict) and 'product' in d:rows.append(d)
 assert len(rows)==n,(folder,len(rows),n)
 for d in rows:
  assert d.get('success') and not d.get('remaining') and not d.get('owned_remaining'),d
  assert all(x['success'] for x in d.get('pressure',[])),d
try:
 run('timing',[sys.executable,T/'runner.py','run',R/'timing']);validate(R/'timing',30)
 run('storage',[sys.executable,T/'retained.py','run',R/'timing/storage']);validate(R/'timing/storage',36)
 for group,source in [('growth','growth.py'),('arrays','arrays.py')]:
  (R/group).mkdir();shutil.copyfile(T/source,R/group/'run.py')
 for mode in ['growth','default','100','random']:
  for p in b.prods:
   folder=R/('growth' if mode=='growth' else 'arrays');cmd=['nsenter','--net=/run/netns/'+b.ns[p],sys.executable,folder/'run.py',p]
   if mode!='growth':cmd.append(mode)
   run('memory-'+mode+'-'+p,cmd)
   f=folder/(p+('' if mode=='growth' else '-'+mode)+'.json');d=json.loads(f.read_text())
   assert not any(d.get(k) for k in ['owned','error','cleanup_error','cleanup_errors']),d
   assert d.get('verified')==50 if mode=='growth' else d.get('success'),d
 (R/'complete.json').write_text(json.dumps(dict(timing_records=30,storage_records=36,memory_cases=24,finished_at=time.time())))
 print('COMPLETE',flush=True)
except BaseException as e:
 (R/'blocked.json').write_text(json.dumps(dict(error=repr(e),time=time.time())));raise
