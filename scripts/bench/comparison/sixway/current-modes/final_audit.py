from pathlib import Path
import argparse,fcntl,json,subprocess,sys,time
B=Path('/home/hong/src/research/report-revision-113');T=B/'tools';sys.path.insert(0,str(T))
from startup import setup
from languages import select_language
from pool_gate import wait
cfg=select_language(json.loads((T/'config.json').read_text()),'python')
p=argparse.ArgumentParser();p.add_argument('--worker');args=p.parse_args()
if args.worker:
 product=args.worker;c,S=setup(product,cfg)
 if product=='kuasar-fork':
  state=json.loads(Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json').read_text())
  ids=[sid for sid,r in state.items() if r.get('pool_state') not in ('ready','preparing','binding','quarantined','network_idle')]
 elif product=='kuasar-mlink':ids=[x['sandboxID'] for x in json.loads(subprocess.check_output(c['ctl']+['list','--json'],text=True))]
 else:
  pager=S.list();ids=[]
  while pager.has_next:ids.extend(x.sandbox_id for x in pager.next_items())
 assert not ids,(product,ids)
 print(json.dumps({'public_instances':ids,'pool':wait(c,64,60)}))
else:
 with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  results={}
  for product in ('kuasar-fork','kuasar-mlink','agentenv','cube','kuasar-off','kuasar-uffd'):
   results[product]=json.loads(subprocess.check_output(['nsenter','--net=/run/netns/'+cfg[product]['netns'],sys.executable,__file__,'--worker',product],text=True))
  nested=Path('/home/hong/src/research/fork-features-113/nested/qemu.pid')
  if nested.exists():assert not Path('/proc',nested.read_text().strip()).exists()
  repos={}
  for name,path in {'kuasar':Path('/home/hong/src/research/python-latest-113/src/kuasar-fork/kuasar-io/kuasar'),'accelerator':B/'accelerator','bench':B/'bench'}.items():
   def git(*a):return subprocess.check_output(['runuser','-u','hong','--','git','-C',str(path),*a],text=True).strip()
   assert git('branch','--show-current')=='sandbox_fork_staging';git('diff','--check')
   repos[name]={'branch':'sandbox_fork_staging','head':git('rev-parse','HEAD'),'status':git('status','--short')}
  (B/'final-audit.json').write_text(json.dumps({'completed_unix':time.time(),'products':results,'repositories':repos,'nested_host_stopped':True,'merged':False},indent=2))
 print('PASS: all six endpoints empty, fork/mlink 64 ready, nested host stopped, staging branches and diffs verified')
