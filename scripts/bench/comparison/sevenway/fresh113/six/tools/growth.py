import sys,time,json,subprocess as sp,fcntl,traceback
from pathlib import Path
D=Path(__file__).resolve().parent
sys.path.insert(0,'/home/hong/src/research/sevenway-current-20261126/six/tools')
import runner as b
if len(sys.argv)>1:
 p=sys.argv[1];b.pr=p;b.setup(p);owned=[];out={'product':p,'samples':[]}
 def save():b.save(D/(p+'.json'),out)
 def sample(n):
  rows=[]
  for _ in range(3):rows.append(b.resources());time.sleep(1)
  out['samples'].append({'instances':n,'time':time.time(),'resources':rows});save()
 try:
  sample(0)
  for i in range(50):
   if int(Path('/proc/meminfo').read_text().split('MemAvailable:')[1].split()[0])<32*1024**2:raise RuntimeError('low available memory')
   s=b.create();owned.append(s);out['owned']=[b.sid(x) for x in owned];save();b.ready(s,'printf READY','READY')
   if (i+1) in [1,10,25,50]:sample(i+1)
  for s in owned:b.ready(s,'printf READY','READY')
  sample(50);out['verified']=50
 except Exception:out['error']=traceback.format_exc()
 finally:
  for s in list(owned):
   try:b.kill(s);owned.remove(s)
   except Exception:out.setdefault('cleanup_errors',[]).append(traceback.format_exc())
  out['owned']=[b.sid(s) for s in owned];save()
 sys.exit(0 if out.get('verified')==50 and not owned else 1)
else:
 with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for p in ['kuasar-mlink','kuasar-off','kuasar-uffd','cube','agentenv']:
   print(p,flush=True);sp.run(['nsenter','--net=/run/netns/'+b.ns[p],sys.executable,__file__,p],check=True)
 (D/'complete.json').write_text('{"verified":250}')
