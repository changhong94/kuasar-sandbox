import resource_worker181 as a
import pathlib,json,time,subprocess as sp,urllib.request,os
assert a.product in ('kuasar-fork','kuasar-mlink')
R=a.R/'measurements/pool-preparation'/a.product;R.mkdir(parents=True,exist_ok=True)
unit='bench108-fork'if a.product=='kuasar-fork'else'bench108-mlink'
events=pathlib.Path('/opt/bench108/data/fork/adapter-state.json.pool-events.jsonl' if a.product=='kuasar-fork' else '/opt/bench108/data/mlink/ttlet.log')
# One warmup plus 20 formal whole-pool preparation measurements.
for i in range(21):
 p=R/f'{i:02d}.json'
 if p.exists():
  assert json.load(open(p)).get('success');continue
 if a.product=='kuasar-fork' and sp.run(['systemctl','is-active','--quiet',unit]).returncode==0:
  req=urllib.request.Request(a.c['api_url']+'/template-pool',headers={'X-API-Key':pathlib.Path(a.c['key_file']).read_text().strip()})
  try:
   with urllib.request.urlopen(req,timeout=3) as f:state=json.load(f)
  except OSError:state={}
  if state.get('ready')==0 and state.get('preparing')==0 and state.get('assigned')==0:
   records=json.load(open('/opt/bench108/data/fork/adapter-state.json'))
   assert all(v.get('pool_state') in ('ready','preparing','reserved','idle','network_idle') for v in records.values()), 'active sandbox must not be interrupted'
   a.b.save(R/('drained-preflight-'+str(time.time_ns())+'.json'),state)
   sp.run(['systemctl','stop',unit],check=True)
 if a.product=='kuasar-fork' and sp.run(['systemctl','is-active','--quiet',unit]).returncode!=0:
  sp.run(['systemctl','stop',unit],check=True)
  env={**os.environ,'CNI_COMMAND':'DEL','CNI_CONTAINERID':'b108seed0001','CNI_NETNS':'/run/netns/b108-fork-seed','CNI_IFNAME':'eth0','CNI_PATH':'/opt/bench108/assets/cni'}
  sp.run(['/opt/bench108/assets/cni/bridge'],input=pathlib.Path('/opt/bench108/deploy/fork/cni.json').read_text(),text=True,env=env,check=True,capture_output=True)
  seed=pathlib.Path('/run/bench108-fork/b108seed0001')
  if seed.exists():
   archive=pathlib.Path('/run/bench108-fork-retired');archive.mkdir(exist_ok=True);seed.rename(archive/('b108seed0001-'+str(time.time_ns())))
  sp.run(['systemctl','start',unit],check=True)
 a.wait(a.c,timeout=600)
 if a.Sandbox:
  # Legacy adapter has no SDK v2 list endpoint; inspect its durable inventory.
  records=json.load(open('/opt/bench108/data/fork/adapter-state.json'))
  ids=[sid for sid,v in records.items() if v.get('pool_state') not in ('ready','preparing','reserved','idle','network_idle')]
  assert not ids,ids
  req=urllib.request.Request(a.c['api_url']+'/template-pool',data=b'{"drain":true}',headers={'X-API-Key':pathlib.Path(a.c['key_file']).read_text().strip(),'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=240) as f:state=json.load(f)
  assert state['ready']==0 and state.get('assigned',0)==0
 else:assert json.loads(sp.check_output(a.c['ctl']+['list','--json']))==[]
 offset=events.stat().st_size;inode=events.stat().st_ino
 with events.open('rb') as f: prefix=f.read(min(offset,256))
 start=time.monotonic_ns();wall=time.time_ns()
 if a.product=='kuasar-fork':
  sp.run(['systemctl','stop',unit],check=True)
  env={**os.environ,'CNI_COMMAND':'DEL','CNI_CONTAINERID':'b108seed0001','CNI_NETNS':'/run/netns/b108-fork-seed','CNI_IFNAME':'eth0','CNI_PATH':'/opt/bench108/assets/cni'}
  sp.run(['/opt/bench108/assets/cni/bridge'],input=pathlib.Path('/opt/bench108/deploy/fork/cni.json').read_text(),text=True,env=env,check=True,capture_output=True)
  seed=pathlib.Path('/run/bench108-fork/b108seed0001')
  if seed.exists():
   archive=pathlib.Path('/run/bench108-fork-retired');archive.mkdir(exist_ok=True)
   seed.rename(archive/('b108seed0001-'+str(time.time_ns())))
  sp.run(['systemctl','start',unit],check=True)
 else:sp.run(['systemctl','restart',unit],check=True)
 # mlink selection is persistent; do not change image-specific policy here.
 state=a.wait(a.c,timeout=600)
 row=dict(iteration=i,warmup=i==0,start_unix_ns=wall,request_to_full_ms=(time.monotonic_ns()-start)/1e6,pool_size=64,prepare_concurrency=8,state=state,success=True)
 with events.open('rb') as f:
  unchanged=events.stat().st_ino==inode and events.stat().st_size>=offset and f.read(len(prefix))==prefix
  f.seek(offset if unchanged else 0);(R/f'{i:02d}-events.jsonl').write_bytes(f.read())
 a.b.save(p,row);print(a.product,i,row['request_to_full_ms'],flush=True)
