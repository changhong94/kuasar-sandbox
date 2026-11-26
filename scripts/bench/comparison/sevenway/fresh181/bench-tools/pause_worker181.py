#!/usr/bin/env python3
import json,pathlib,time,uuid,shlex,urllib.request,argparse,hashlib,statistics,os
from e2b import Sandbox
os.environ.update(NO_PROXY='*',no_proxy='*')
import resource_worker181 as adapter
from types import SimpleNamespace
class CLI:
 def __init__(self,s):self.raw=s;self.sandbox_id=s;self.commands=self
 def run(self,command,background=False,on_stdout=None,**kw):
  if background:
   pid=int(adapter.cmd(self.raw,'nohup '+command.removeprefix('exec ')+' </dev/null >/tmp/bench-keeper.out 2>&1 & echo $!'))
   return SimpleNamespace(pid=pid)
  stdout=adapter.stream_cmd(self.raw,command,on_stdout) if on_stdout else adapter.cmd(self.raw,command)
  return SimpleNamespace(exit_code=0,stdout=stdout,stderr='')
def wrap(s):return s if adapter.Sandbox else CLI(s)
def raw(s):return s if adapter.Sandbox else s.raw
a=SimpleNamespace(count=50,drop_caches=False,output=str(adapter.R/'measurements/pause-restore'/ (adapter.product+'.json')))
pathlib.Path(a.output).parent.mkdir(parents=True,exist_ok=True)
def py(s,code):
 return adapter.cmd(raw(s),'/usr/local/bin/python3 -c '+shlex.quote(code))
IO="""import hashlib,time,json,os
h=hashlib.sha256();t=time.monotonic()
with open('/tmp/fiveway.bin','wb') as f:
 for i in range(32):
  b=hashlib.shake_256(('fiveway'+str(i)).encode()).digest(1048576);h.update(b);f.write(b)
 f.flush();os.fsync(f.fileno())
print(json.dumps([h.hexdigest(),(time.monotonic()-t)*1000]))"""
KEEPER="""import os,time,hashlib,json
blob=os.urandom(32*1024*1024)
i=0
while True:
 i+=1
 with open('/tmp/keeper.next','w') as f:json.dump([os.getpid(),i,hashlib.sha256(blob).hexdigest()],f)
 os.replace('/tmp/keeper.next','/tmp/keeper.json')
 time.sleep(.2)
"""
rows=json.load(open(a.output)).get('samples',[]) if pathlib.Path(a.output).exists() else []
for i in range(a.count+1):
 if any(x['iteration']==i and x.get('success') and x.get('delete_ack') for x in rows):continue
 adapter.wait(adapter.c)
 s=None;row={'iteration':i,'warmup':i==0,'drop_caches':a.drop_caches,'success':False}
 try:
  s=wrap(adapter.create());row['id']=s.sandbox_id
  checksum,io_ms=json.loads(py(s,IO));row['io_ms']=io_ms
  if adapter.product=='kuasar-fork':
   # The legacy streaming RPC holds its lifecycle guard until process exit.
   # Detach the guest keeper with closed stdio; the short launcher exits first.
   pid=int(adapter.cmd(raw(s),'nohup /usr/local/bin/python3 -c '+shlex.quote(KEEPER)+' </dev/null >/tmp/bench-keeper.out 2>&1 & echo $!').strip())
   row['worker_pid']=pid
  else:
   worker=s.commands.run('exec /usr/local/bin/python3 -c '+shlex.quote(KEEPER),user='root',cwd='/',background=True,timeout=600)
   row['worker_pid']=worker.pid
  for _ in range(100):
   r=s.commands.run('cat /tmp/keeper.json 2>/dev/null || true',user='root',cwd='/')
   if r.stdout.strip():before=json.loads(r.stdout);break
   time.sleep(.02)
  else:raise TimeoutError('keeper')
  # Preparation-only liveness check: require actual counter progress.
  for _ in range(50):
   time.sleep(.2);advanced=json.loads(py(s,"print(open('/tmp/keeper.json').read())"))
   if advanced[1]>before[1]:break
  else:raise AssertionError('keeper not progressing before pause within 10s')
  before=advanced
  t=time.perf_counter_ns();adapter.pause(raw(s));row['save_ms']=(time.perf_counter_ns()-t)/1e6
  row['saved_state']='pause API acknowledged'
  marker='READY_'+uuid.uuid4().hex;native='NATIVE_'+uuid.uuid4().hex;chunks=[];seen=[];ready=[];t=time.perf_counter_ns()
  s=wrap(adapter.resume(raw(s)));row['restore_api_ms']=(time.perf_counter_ns()-t)/1e6
  def got(x):
   chunks.append(x)
   if native+'\n' in ''.join(chunks) and not ready:ready.append(time.perf_counter_ns())
   if marker+'\n' in ''.join(chunks) and not seen:seen.append(time.perf_counter_ns())
  r=s.commands.run('printf "%s\\n" '+shlex.quote(native)+'; exec /usr/local/bin/python3 -c '+shlex.quote('import sys; print(sys.argv[1], flush=True)')+' '+marker,user='root',cwd='/',on_stdout=got,timeout=120);assert r.exit_code==0 and seen
  assert ready
  row['shell_ready_ms']=(ready[0]-t)/1e6
  row['restore_print_ms']=(seen[0]-t)/1e6
  row['pager_modes']=[bool(json.loads(p.read_text()).get('local_file_plan', False)) for p in pathlib.Path('/run/fork2').rglob('memory-ranges.manifest.json')]
  after=json.loads(py(s,"print(open('/tmp/keeper.json').read())"));assert after[0]==before[0] and after[2]==before[2]
  for _ in range(50):
   time.sleep(.2);later=json.loads(py(s,"print(open('/tmp/keeper.json').read())"))
   if later[1]>after[1]:break
  else:raise AssertionError('restored keeper did not progress within 10s')
  assert py(s,"import hashlib;print(hashlib.sha256(open('/tmp/fiveway.bin','rb').read()).hexdigest())")==checksum
  row.update(success=True,process_continued=True,file_verified=True)
 except Exception as e:row['error']=str(e);raise
 finally:
  if s:
   try:adapter.b.kill(raw(s));row['delete_ack']=True
   except Exception as e:row['cleanup_error']=str(e)
  rows.append(row);pathlib.Path(a.output).write_text(json.dumps({'image_digest':adapter.cfg['_languages']['python']['digest'],'samples':rows},indent=2));print(json.dumps(row),flush=True)
for k in ('save_ms','restore_api_ms','restore_print_ms'):
 v=[r[k] for r in rows if not r['warmup']];print(k,statistics.median(v),max(v),flush=True)
