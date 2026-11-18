from pathlib import Path
import fcntl,json,subprocess as sp,time,shutil
B=Path('/home/hong/src/research/report-revision-113');T=B/'tools';cfg=json.loads((T/'config.json').read_text())
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 c=cfg['kuasar-mlink'];ctl=['nsenter','--net=/run/netns/'+c['netns']]+c['ctl']
 for _ in range(120):
  r=sp.run(ctl+['list','--json'],capture_output=True,text=True)
  if r.returncode==0:
   assert json.loads(r.stdout)==[];break
  time.sleep(.5)
 else:raise TimeoutError('owned mlink API readiness')
 sp.run(['python3',str(T/'switch-language.py'),str(T/'config.json'),'python',str(B/'results/preparation/python')],check=True)
 rows={}
 for name in ['kuasar-fork','kuasar-mlink']:
  code="import sys,json;sys.path.insert(0,"+repr(str(T))+");from pool_gate import wait;c=json.load(open("+repr(str(T/'config.json'))+"));print(json.dumps(wait(c["+repr(name)+"],capacity=64,timeout=600)))"
  rows[name]=json.loads(sp.check_output(['nsenter','--net=/run/netns/'+cfg[name]['netns'],'python3','-c',code],text=True))
 (B/'formal-profile.json').write_text(json.dumps({'capacity':64,'states':rows},indent=2))
 shutil.copyfile('/home/hong/src/research/startup-modes-113/progress',B/'progress');(B/'progress').chmod(0o755)
 print('both owned pools verified at 64 ready slots')
