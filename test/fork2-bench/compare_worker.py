#!/usr/bin/env python3
"""Persistent matched SDK worker; stdin requests, stdout JSON results, no secrets."""
import os,sys,json,pathlib,time,uuid,shlex,urllib.request,sqlite3
os.environ.update(NO_PROXY='*',no_proxy='*')
from e2b import Sandbox
kind=sys.argv[1]
if kind=='old':
 root=pathlib.Path('/srv/fork-compare-old');api='http://127.0.0.1:19220';key=(root/'deploy/fork/api-key').read_text().strip();template='python';proxy=api
else:
 c=json.loads(pathlib.Path('/srv/fork2/console.json').read_text());api=c['api'];key=c['key'];proxy='http://127.0.0.1:19211';template=json.loads(pathlib.Path('/srv/fork2/data/registry/python.json').read_text())['template_id']
opts=dict(api_key=key,api_url=api,sandbox_url=proxy)
def gate():
 end=time.monotonic()+120
 while time.monotonic()<end:
  if kind=='old':
   with urllib.request.urlopen(urllib.request.Request(api+'/template-pool',headers={'X-API-Key':key}),timeout=5) as f:d=json.load(f)
   if d['ready']==2 and d['assigned']==0 and not d['preparing']:return
  else:
   with sqlite3.connect('file:/srv/fork2/data/base/node-ctl.db?mode=ro',uri=True) as db:
    n=db.execute('select count(*) from prepared_vm_leases p join run_pool_ownership o on p.run_id=o.run_id').fetchone()[0]
   if n==2:return
  time.sleep(.02)
 raise TimeoutError('pool not ready')
print(json.dumps({'worker':kind,'ready':True}),flush=True)
for line in sys.stdin:
 req=json.loads(line)
 if req is None:break
 s=None;row={'product':kind,'iteration':req['iteration'],'warmup':req['iteration']==0,'success':False}
 try:
  gate();marker='READY_'+uuid.uuid4().hex;chunks=[];seen=[]
  command='exec /usr/local/bin/python3 -c '+shlex.quote('import sys; print(sys.argv[1], flush=True)')+' '+marker
  def receive(x):
   chunks.append(x)
   if marker+'\n' in ''.join(chunks) and not seen:seen.append(time.perf_counter_ns())
  t=time.perf_counter_ns();row['start_ns']=t
  s=Sandbox.create(template,timeout=300,**opts);row['id']=s.sandbox_id;row['api_ms']=(time.perf_counter_ns()-t)/1e6
  r=s.commands.run(command,user='root',cwd='/',timeout=60,on_stdout=receive)
  assert r.exit_code==0 and seen
  row['print_ms']=(seen[0]-t)/1e6
  # Diagnostic only, after the first print's measurement has ended.
  seen.clear();chunks.clear();t=time.perf_counter_ns()
  r=s.commands.run(command,user='root',cwd='/',timeout=60,on_stdout=receive);assert r.exit_code==0 and seen
  row['second_python_ms']=(seen[0]-t)/1e6;row['success']=True
 except Exception as e:row['error']=repr(e)
 finally:
  if s:
   try:s.kill();row['deleted']=True
   except Exception as e:row['delete_error']=repr(e)
 print(json.dumps(row),flush=True)
