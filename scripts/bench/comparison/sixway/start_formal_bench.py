#!/usr/bin/env python3
"""Six-way extension of the frozen five-way protocol. No global cache drops."""
from pathlib import Path
import sys,subprocess as sp,json,time,hashlib,shutil,os,argparse
D=Path('/home/hong/deploy/comparison/sixway');sys.path.insert(0,str(D));import baseline_config as cfg
PRODUCTS=cfg.PRODUCTS+('kuasar-fork',);NS={**cfg.NAMESPACES,'kuasar-fork':'bench113-fork'}
PYTHON=cfg.PYTHON if hasattr(cfg,'PYTHON') else cfg.DEPLOY/'venv/bin/python'
def save(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')
def phase(root,name,command):
 save(root/'progress.json',{'phase':name,'started_at':time.time()});print('START',name,flush=True)
 with (root/(name+'.log')).open('w') as log:
  rc=sp.run(list(map(str,command)),stdout=log,stderr=sp.STDOUT,env={**os.environ,'FIVEWAY_LOCK_HELD':'1'}).returncode
 if rc:
  save(root/'blocked.json',{'phase':name,'exit_code':rc});raise RuntimeError(name+' failed; preserve owned ledgers and inspect before resuming')
 print('END',name,flush=True)
def validate(directory,count):
 rows=[]
 for f in directory.glob('*.json'):
  d=json.loads(f.read_text())
  if isinstance(d,dict) and 'product' in d:rows.append(d)
 assert len(rows)==count,(str(directory),len(rows),count)
 for d in rows:
  assert d.get('success') and not d.get('owned_remaining') and not d.get('remaining'),d.get('product')
  assert all(x.get('success') for x in d.get('pressure',[])),d.get('product')
 return len(rows)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',action='store_true');ap.add_argument('--output',type=Path);args=ap.parse_args()
 root=args.output or cfg.HOME/'results'/('sixway-matched-'+time.strftime('%Y%m%d_%H%M%S'))
 print('Products:',PRODUCTS,'Output:',root,flush=True)
 if not args.start:return
 lock=cfg.lock()
 for p in cfg.PRODUCTS:cfg.require_idle(p)
 assert json.loads(Path('/home/hong/data/kuasar-fork/adapter-state.json').read_text())=={},'fork backend busy'
 sp.run(['systemctl','is-active','--quiet','bench-kuasar-fork'],check=True)
 identity=json.loads(Path('/home/hong/deploy/kuasar-fork-research/image-identity.json').read_text())
 assert identity['base_manifest_digest']=='sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79'
 assert identity['python']=='Python 3.12.14'
 with open('/home/hong/data/kuasar-fork/guest/rootfs.ext4','rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==identity['image_sha256']
 import tomllib
 conf=tomllib.loads((cfg.HOME/'data/mlink3/ttlet.toml').read_text())
 def values(d,k):return [v for a,v in d.items() if a==k]+[n for v in d.values() if isinstance(v,dict) for n in values(v,k)]
 assert values(conf,'foreground_quiet_period_ms')==[1000] and values(conf,'cleanup_concurrency')==[16]
 root.mkdir(parents=True,exist_ok=False);tools=root/'tools';tools.mkdir();save(root/'image-identity.json',identity)
 files=['runner.py','retained.py','extent_accounting.py','summarize.py','storage-summary.py','preflight.py','mlink_policy.py']
 for f in files:shutil.copy2(D/f,tools/f)
 save(root/'workload-hashes.json',{f:hashlib.sha256((tools/f).read_bytes()).hexdigest() for f in files})
 save(root/'scope.json',{'products':PRODUCTS,'reference':'kuasar-mlink','prefetch':'off','cpu':1,'memory_mib':2048,'quiet_period_ms':1000,'cleanup_concurrency':16,'timing_rounds':5,'storage_rounds':3,'models_used':False,'fork_unsupported':['persistent_pause_resume'],'fork_filesystem':'read-only root with guest RAM overlay','baseline_source':'/home/hong/results/fiveway-matched-20261113_075338/tools','sdk_version':'2.25.1'})
 policy=None
 try:
  import mlink_policy
  policy=mlink_policy.prepare(root/'mlink-policy.json')
  pre=root/'preflight';pre.mkdir()
  for p in PRODUCTS:phase(root,'preflight-'+p,['nsenter','--net=/run/netns/'+NS[p],PYTHON,tools/'preflight.py',p,pre/(p+'.json')])
  phase(root,'timing',[PYTHON,tools/'runner.py','run',root/'timing']);validate(root/'timing',30)
  for f in (root/'timing').glob('[1-5]-*.json'):assert 'Python 3.12.14' in json.loads(f.read_text())['platform'],str(f)
  phase(root,'storage',[PYTHON,tools/'retained.py','run',root/'timing/storage']);validate(root/'timing/storage',36)
  phase(root,'timing-summary',[PYTHON,tools/'summarize.py',root/'timing'])
  phase(root,'storage-summary',[PYTHON,tools/'storage-summary.py',root/'timing/storage'])
  for group in ['growth','arrays']:
   target=root/group;target.mkdir();source=(D/group/'run.py').read_text().replace(str(D),str(tools));(target/'run.py').write_text(source)
  for mode in ['growth','default','100','random']:
   for p in PRODUCTS:
    directory=root/('growth' if mode=='growth' else 'arrays');cmd=['nsenter','--net=/run/netns/'+NS[p],PYTHON,directory/'run.py',p]
    if mode!='growth':cmd.append(mode)
    phase(root,'memory-'+mode+'-'+p,cmd)
    d=json.loads((directory/(p+('' if mode=='growth' else '-'+mode)+'.json')).read_text())
    assert not any(d.get(k) for k in ['owned','error','cleanup_error','cleanup_errors']),p
    assert d.get('verified')==50 if mode=='growth' else d.get('success'),p
  save(root/'workloads-complete.json',{'timing_records':30,'storage_records':36,'memory_cases':24,'finished_at':time.time()})
 except BaseException as error:
  if not (root/'blocked.json').exists():save(root/'blocked.json',{'error':str(error),'time':time.time()})
  raise
 finally:
  if policy is None and (root/'mlink-policy.json').exists():policy=json.loads((root/'mlink-policy.json').read_text())
  if policy is not None:
   mlink_policy.restore(policy)
   save(root/'mlink-policy-restored.json',{'restored':True,'time':time.time()})
 save(root/'complete.json',json.loads((root/'workloads-complete.json').read_text()))
 print('Completed',root,flush=True)
if __name__=='__main__':main()
