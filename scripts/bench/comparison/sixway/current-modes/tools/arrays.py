import sys,time,statistics as st,concurrent.futures as cf,subprocess as sp,json,shlex,fcntl,os,traceback
from pathlib import Path
d=Path(__file__).resolve().parent
sys.path.insert(0,'/home/hong/src/research/report-revision-113/tools')
import runner as b
if len(sys.argv)==1:
 with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  for mode in ['random','100','default']:
   for p in b.prods:
    print(mode,p,flush=True)
    f='pinned.py' if p in ('kuasar-off','kuasar-uffd') else 'run.py'
    sp.run(['nsenter','--net=/run/netns/'+b.ns[p],sys.executable,str(d/f),p,mode])
 sys.exit()
p,mode=sys.argv[1:];b.pr=p;b.setup(p);owned=[];out={};path=d/(p+'-'+mode+'.json')
try:
 out['zero']=b.resources()['pss_mib']
 for i in range(50):
  if int(Path('/proc/meminfo').read_text().split('MemAvailable:')[1].split()[0])<32*1024**2:raise RuntimeError('low host memory')
  s=b.create();owned.append(s);out['owned']=[b.sid(x) for x in owned];b.save(path,out);b.ready(s,'printf READY','READY')
 out['ready']=b.resources()['pss_mib']
 for phase in ['python',mode]:
  def work(s):
   code="""import os,time
a=None
if MODE!='python':
 a=bytearray(20971520)
 if MODE in ('random','100'):
  for i in range(0,len(a),65536):a[i:i+65536]=os.urandom(65536) if MODE=='random' else bytes([100])*65536
time.sleep(15)
print(0 if a is None else len(a))""".replace('MODE',repr(phase))
   start=time.monotonic();ret=b.py(s,code);end=time.monotonic()
   assert ret==('0' if phase=='python' else '20971520')
   return [start,end]
  with cf.ThreadPoolExecutor(50) as pool:
   jobs=[pool.submit(work,s) for s in owned]; samples=[]
   while not all(j.done() for j in jobs):
    t=time.monotonic();v=b.resources()['pss_mib'];samples.append([t,time.monotonic(),v]);time.sleep(.4)
   ts=[j.result() for j in jobs]
  left=max(e for _,e in ts)-14;right=min(e for _,e in ts)-1
  vv=[v for a,z,v in samples if a>=left and z<=right];assert len(vv)>=3,(left,right,len(vv))
  out[phase]=st.median(vv);out[phase+'_samples']=samples;out[phase+'_intervals']=ts
 out['success']=True
except Exception:out['error']=traceback.format_exc()
finally:
 for s in list(owned):
  try:b.kill(s);owned.remove(s)
  except Exception:out['cleanup_error']=traceback.format_exc()
 out['owned']=[b.sid(s) for s in owned];b.save(path,out)
