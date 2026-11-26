import os
import os,json,time,pathlib,urllib.request,fcntl,traceback,sys,base64,subprocess
from cache_state import residency,verified_warm
from e2b import Sandbox
import baseline_startup as bench
R=pathlib.Path('/home/hong/src/research/sevenway-current-20261126/fork2');mode=sys.argv[1];assert mode in ['local','remote'];out=R/'results'/('snapshot-'+mode);out.mkdir(exist_ok=True)
lock=open('/run/skyrl-threeway-benchmark.lock','a');(None if os.environ.get("FORK2_FULL_LOCK_HELD")=="1" else fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB))
a=json.load(open('/srv/fork2/console.json'));opts=dict(api_key=a['key'],api_url=a['api'],sandbox_url='http://127.0.0.1:19211')
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix('.tmp');q.write_text(json.dumps(x,indent=2));q.replace(p)
def gate(c=None):
 start=time.monotonic()
 import sqlite3
 while time.monotonic()-start<180:
  with sqlite3.connect('file:/home/hong/src/research/fork2-control-persistent/node-ctl.db?mode=ro',uri=True)as db:
   ids=[r[0]for r in db.execute('select run_id from prepared_vm_leases')];n=db.execute('select count(*) from sandboxes').fetchone()[0]
  if len(ids)==64 and n==0:
   pressure=json.loads(subprocess.check_output(['curl','-sf','--max-time','3','--unix-socket','/run/fork2/node.sock','http://localhost/internal/admin/resource-pressure']))
   if any(p.get('name')=='prepared' and p.get('states')=={'idle':64} for p in pressure['runner_pools']):return {'ready':64,'elapsed_ms':(time.monotonic()-start)*1000}
  time.sleep(.1)
 raise TimeoutError('64 ready slots')
bench.pool_wait=gate
key=R/'private-api-key';key.write_text(a['key']);key.chmod(0o600)
c=dict(kind='e2b',api_url=a['api'],sandbox_url=opts['sandbox_url'],key_file=str(key));bench.setup('fork2',{'fork2':c})
cache='/srv/fork2/bin/cache-ctl-sevenway';endpoint='unix:///run/fork2-sevenway-cache/health.sock'
def cache_stats():
 info=json.loads(subprocess.check_output([cache,'info','--endpoint',endpoint,'--json'],text=True))
 pid=int(subprocess.check_output(['systemctl','show','fork2-sevenway-cache','-p','MainPID','--value'],text=True))
 io={k:int(v)for k,v in (line.split(':',1)for line in pathlib.Path('/proc',str(pid),'io').read_text().splitlines())}
 return {'info':info,'disk_read_bytes':io['read_bytes']}

def memory_paths():
 paths=set()
 for p in pathlib.Path('/proc').glob('[0-9]*'):
  try:
   if 'fork2-' not in (p/'cgroup').read_text():continue
   for line in (p/'maps').read_text().splitlines():
    cols=line.split(None,5)
    if len(cols)<6:continue
    raw=cols[5]
    if raw.startswith('/srv/fork2/data/') and (raw.endswith('.snapshot')or '/template-memory-cache-v2/'in raw):
     f=pathlib.Path(raw)
     if f.is_file():paths.add(f)
  except (OSError,PermissionError):pass
 return paths
label=sys.argv[2]
for lang in ['python','node','ruby']:
 template=json.load(open(R/'results/snapshot-local'/lang/'template.json'))
 paths=[pathlib.Path(p) for p in json.load(open(R/'results/snapshot-local'/lang/'target-paths.json'))]
 c['template']=template['templateID'];c['create_kwargs']={'metadata':template.get('metadata',{})}
 cfg={'fork2':c,'_language':lang,'_image_digest':template['image_digest']}
 for i in range(51):
  gate();proof=verified_warm(sorted(paths));target=R/'results/snapshot-start3-opt'/label/lang/f'{i:02}.json'
  target.parent.mkdir(parents=True,exist_ok=True)
  bench.sample('fork2',cfg,target,c,Sandbox)
  row=json.loads(target.read_text());row.update(iteration=i,warmup=i==0,cache_preparation=proof);save(target,row)
  print(label,lang,i,row['success'],row.get('interpreter_print_ms'),flush=True)
  assert row['success'] and row['destroyed']
