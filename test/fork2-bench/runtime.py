#!/usr/bin/env python3
"""Use the exact 108 historical CPU/IO payloads; only the fork2 API is used."""
import ast,json,pathlib,statistics,time,hashlib,shlex,argparse,os
from e2b import Sandbox
os.environ.update(NO_PROXY='*',no_proxy='*')
p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=10);p.add_argument('--output',required=True);a=p.parse_args()
reference=pathlib.Path('/home/huawei/codex-work/local-cow-space-108/evidence-durable/after/runner.py')
work={}
for node in ast.parse(reference.read_text()).body:
 if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant):
  for t in node.targets:
   if isinstance(t,ast.Name) and t.id in ('CPU','IO'):work[t.id]=node.value.value
assert set(work)=={'CPU','IO'}
c=json.loads(pathlib.Path('/srv/fork2/console.json').read_text());im=json.loads(pathlib.Path('/srv/fork2/data/registry/python.json').read_text())
opts=dict(api_key=c['key'],api_url=c['api'],sandbox_url='http://127.0.0.1:19211')
cpu_expected=hashlib.sha256(hashlib.shake_256(b'perf-cpu-v1').digest(1048576)*256).hexdigest()
h=hashlib.sha256()
for i in range(32):h.update(hashlib.shake_256(('fiveway'+str(i)).encode()).digest(1048576))
rows=[]
for i in range(a.count+1):
 s=None
 try:
  s=Sandbox.create(template=im['template_id'],timeout=300,**opts)
  def run(cmd):
   r=s.commands.run(cmd,user='root',cwd='/',timeout=120);assert r.exit_code==0,r.stderr;return r.stdout.strip()
  run('true') # admission/first command is measured by startup.py, not short-exec
  short=[]
  for _ in range(8):
   t=time.perf_counter_ns();run('true');short.append((time.perf_counter_ns()-t)/1e6)
  cpu=json.loads(run('/usr/local/bin/python3 -c '+shlex.quote(work['CPU'])))
  io=json.loads(run('/usr/local/bin/python3 -c '+shlex.quote(work['IO'])))
  assert cpu[0]==cpu_expected and io[0]==h.hexdigest()
  row=dict(iteration=i,warmup=i==0,short_ms=short,short_median_ms=statistics.median(short),cpu_ms=cpu[1],cpu_process_ms=cpu[2],io_ms=io[1],hash_verified=True,load=os.getloadavg())
 finally:
  if s:s.kill()
 rows.append(row);print(json.dumps(row),flush=True)
 pathlib.Path(a.output).write_text(json.dumps({'image_digest':im['manifest'],'reference':str(reference),'workloads':work,'samples':rows},indent=2))
for k in ('short_median_ms','cpu_ms','io_ms'):
 v=[r[k] for r in rows if not r['warmup']];print(k,statistics.median(v),max(v),flush=True)
