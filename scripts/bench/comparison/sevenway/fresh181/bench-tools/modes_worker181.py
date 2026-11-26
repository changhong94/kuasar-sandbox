from pathlib import Path
import sys,json,base64,time,subprocess
from baseline_startup import setup,sample
from cache_state181 import condition
from chunk_sources181 import source_delta
R=Path('/home/hong/codex-work/sevenway-fresh-181');product,lang,mode=sys.argv[1:];cfg=json.load(open(R/'tools/config.json'))
cfg[product]['template']=cfg['_languages'][lang]['templates'][product];cfg['_language']=lang;cfg['_image_digest']=cfg['_languages'][lang]['digest'];paths=[]
assert product in ('kuasar-off','kuasar-uffd','kuasar-fork')
suffix=product.rsplit('-',1)[1];access=json.load(open('/opt/bench108/deploy/'+suffix+'/access.json')) if product!='kuasar-fork' else {}
if product=='kuasar-fork':
 subprocess.run(['python3',str(R/'tools/repair-old-disks181.py')],check=True)
 if mode.startswith('local_'):
  entry=json.load(open('/opt/bench108/data/fork/adapter-state.json.snapshot-preparation.json'))[cfg[product]['template']]
  paths=sorted(p for p in Path(entry['directory']).iterdir()if p.is_file());assert paths
 else:cfg[product]['create_kwargs']={'metadata':{'kuasar.snapshot.mode':'manifest'}}
else:
 if mode.startswith('local_'):
  entry=next(x for x in json.load(open(R/(product+'-native.json')))if x['language']==lang)
  ref=entry['result']['snapshotRef'];cfg[product]['template']='e2b-snp-'+base64.urlsafe_b64encode(ref.encode()).decode().rstrip('=')
  directory=Path(entry['directory']);names=[entry['result'][k].split('@',1)[0][7:]for k in ('snapshotRef','sandboxRef')]
  paths=sorted({*(directory/name for name in names),*directory.glob('*.image')});assert paths and all(p.is_file()for p in paths)
c,Sandbox=setup(product,cfg)
def cache_info():
 binary='/srv/fork2/bin/cache-ctl' if product=='kuasar-fork' else str(Path(access['bin'])/'cache-ctl');root='/opt/bench108/data/'+suffix
 info=json.loads(subprocess.check_output([binary,'info','--endpoint',('unix:///run/sevenway181-old-cache-health.sock' if product=='kuasar-fork' else 'unix://'+root+'/run/cache-health.sock'),'--json'],text=True))
 io={}
 for p in Path('/proc').glob('[0-9]*'):
  try:
   cmd=(p/'cmdline').read_bytes()
   if b'cache-ctl'not in cmd or (str(R/'old-private/cache.yaml').encode() if product=='kuasar-fork' else str(Path(root).resolve()).encode())not in cmd:continue
   io[p.name]={k:int(v)for k,v in (l.split(':')for l in (p/'io').read_text().splitlines())}
  except OSError:pass
 assert io,'cache IO accounting unavailable'
 return dict(info=info,process_io=io,backend='rocksdb')
out=R/'measurements/snapshot-modes'/lang/product/mode;out.mkdir(parents=True,exist_ok=True)
for i in range(51):
 p=out/f'{i:02}.json'
 if p.exists():
  old=json.load(open(p))
  if old.get('success')and old.get('destroyed'):continue
  raise RuntimeError('review failed snapshot sample '+str(p))
 proof=condition(paths,mode) if paths else None
 before=cache_info() if mode=='remote'else None;observed=[]
 if before:c['startup_complete_observer']=lambda:observed.append(cache_info())
 ok=sample(product,cfg,p,c,Sandbox);d=json.load(open(p));d.update(mode=mode,warmup=i==0,cache_preparation=proof)
 if before:
  assert observed;after=observed[0];assert set(before['process_io'])==set(after['process_io'])
  d['remote_cache']=dict(before=before,after=after,cache_daemon_disk_read_bytes=sum(after['process_io'][pid]['read_bytes']-v['read_bytes']for pid,v in before['process_io'].items()))
  try:d['remote_cache']['source_percentages']=source_delta(before,after)
  except AssertionError:d['remote_cache']['source_percentages_unavailable']='Installed baseline cache lacks chunk source counters; instrumentation follow-up required'
 p.write_text(json.dumps(d,indent=2));print(product,lang,mode,i,ok,flush=True);assert ok
