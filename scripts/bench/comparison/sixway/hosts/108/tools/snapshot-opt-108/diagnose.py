import os,time,json,concurrent.futures,uuid
from pathlib import Path
M=Path('/opt/bench108');os.environ.update(E2B_API_KEY=(M/'deploy/fork/api-key').read_text().strip(),E2B_API_URL='http://127.0.0.1:18887',E2B_SANDBOX_URL='http://127.0.0.1:18887',NO_PROXY='*')
from e2b import Sandbox
rows=[]
def sample(i):
 t=time.perf_counter_ns();s=Sandbox.create('base',timeout=60)
 try:
  created=time.perf_counter_ns();mark='READY_'+uuid.uuid4().hex;r=s.commands.run('printf '+mark,user='root',timeout=20);assert r.stdout==mark
  return dict(sid=s.sandbox_id,create_ms=(created-t)/1e6,ready_ms=(time.perf_counter_ns()-t)/1e6)
 finally:s.kill()
with concurrent.futures.ThreadPoolExecutor(2) as p:
 for i in range(2):rows.extend(p.map(sample,range(2)));time.sleep(2)
(M/'results/snapshot-opt-108/diagnostic.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
