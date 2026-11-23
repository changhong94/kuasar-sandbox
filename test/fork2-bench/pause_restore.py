#!/usr/bin/env python3
import json,pathlib,time,uuid,shlex,urllib.request,argparse,hashlib,statistics,os
from e2b import Sandbox
os.environ.update(NO_PROXY='*',no_proxy='*')
p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=10);p.add_argument('--output',required=True);p.add_argument('--drop-caches',action='store_true');a=p.parse_args()
c=json.loads(pathlib.Path('/srv/fork2/console.json').read_text());im=json.loads(pathlib.Path('/srv/fork2/data/registry/python.json').read_text());opts=dict(api_key=c['key'],api_url=c['api'],sandbox_url='http://127.0.0.1:19211')
def req(method,path,data=None):
 r=urllib.request.Request(c['api']+path,method=method,data=None if data is None else json.dumps(data).encode(),headers={'X-API-Key':c['key'],'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=240) as f:
  b=f.read();return json.loads(b) if b else None
def py(s,code):
 r=s.commands.run('/usr/local/bin/python3 -c '+shlex.quote(code),user='root',cwd='/',timeout=120)
 assert r.exit_code==0,r.stderr
 return r.stdout.strip()
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
rows=[]
for i in range(a.count+1):
 s=None;row={'iteration':i,'warmup':i==0,'drop_caches':a.drop_caches,'success':False}
 try:
  s=Sandbox.create(template=im['template_id'],timeout=600,**opts);row['id']=s.sandbox_id
  checksum,io_ms=json.loads(py(s,IO));row['io_ms']=io_ms
  worker=s.commands.run('exec /usr/local/bin/python3 -c '+shlex.quote(KEEPER),user='root',cwd='/',background=True,timeout=600)
  row['worker_pid']=worker.pid
  for _ in range(100):
   r=s.commands.run('cat /tmp/keeper.json 2>/dev/null || true',user='root',cwd='/')
   if r.stdout.strip():before=json.loads(r.stdout);break
   time.sleep(.02)
  else:raise TimeoutError('keeper')
  time.sleep(.3)
  advanced=json.loads(py(s,"print(open('/tmp/keeper.json').read())"));assert advanced[1]>before[1], 'keeper not progressing before pause'
  before=advanced
  t=time.perf_counter_ns();req('POST','/sandboxes/'+s.sandbox_id+'/pause',{'memory':True, 'checkpoint_drop_caches':a.drop_caches});row['save_ms']=(time.perf_counter_ns()-t)/1e6
  row['saved_state']=req('GET','/sandboxes/'+s.sandbox_id).get('state')
  marker='READY_'+uuid.uuid4().hex;native='NATIVE_'+uuid.uuid4().hex;chunks=[];seen=[];ready=[];t=time.perf_counter_ns()
  s=Sandbox.connect(s.sandbox_id,timeout=600,**opts);row['restore_api_ms']=(time.perf_counter_ns()-t)/1e6
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
   try:s.kill();row['delete_ack']=True
   except Exception as e:row['cleanup_error']=str(e)
  rows.append(row);pathlib.Path(a.output).write_text(json.dumps({'image_digest':im['manifest'],'samples':rows},indent=2));print(json.dumps(row),flush=True)
for k in ('save_ms','restore_api_ms','restore_print_ms'):
 v=[r[k] for r in rows if not r['warmup']];print(k,statistics.median(v),max(v),flush=True)
