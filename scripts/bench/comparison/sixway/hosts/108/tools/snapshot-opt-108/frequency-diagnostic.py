import os,json,time,threading,concurrent.futures
from pathlib import Path
M=Path('/opt/bench108');os.environ.update(E2B_API_KEY=(M/'deploy/fork/api-key').read_text().strip(),E2B_API_URL='http://127.0.0.1:18887',E2B_SANDBOX_URL='http://127.0.0.1:18887',NO_PROXY='*')
from e2b import Sandbox
records=json.loads((M/'data/fork/adapter-state.json').read_text());pids=[r['pid'] for r in sorted((r for r in records.values() if r.get('pool_state')=='ready'),key=lambda r:r['pool_ready_ns'])[:2]]
stop=threading.Event();samples=[]
def watch():
 while not stop.is_set():
  row={'ns':time.perf_counter_ns(),'frequencies':[],'threads':[]}
  for cpu in range(8):
   row['frequencies'].append(int(Path(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq').read_text()))
  for pid in pids:
   for p in Path(f'/proc/{pid}/task').iterdir():
    try:
     s=(p/'stat').read_text();f=s.rsplit(') ',1)[1].split();row['threads'].append([pid,p.name,s.split('(',1)[1].rsplit(')',1)[0],int(f[36])])
    except FileNotFoundError:pass
  samples.append(row);stop.wait(.002)
def sample(i):
 t=time.perf_counter_ns();s=Sandbox.create('base',timeout=60)
 try:
  c=time.perf_counter_ns();r=s.commands.run('printf FREQ_READY',user='root',timeout=20);assert r.stdout=='FREQ_READY';return dict(sid=s.sandbox_id,start_ns=t,created_ns=c,ended_ns=time.perf_counter_ns())
 finally:s.kill()
time.sleep(2);thread=threading.Thread(target=watch);thread.start()
try:
 with concurrent.futures.ThreadPoolExecutor(2) as pool:rows=list(pool.map(sample,range(2)))
finally:stop.set();thread.join()
(M/'results/snapshot-opt-108/frequency-diagnostic.json').write_text(json.dumps({'rows':rows,'samples':samples}));print(rows)
