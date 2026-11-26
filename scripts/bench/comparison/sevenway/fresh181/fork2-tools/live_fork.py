import os
#!/usr/bin/env python3
"""Independent fork2 only: inherited disk, independent mutation and deletion."""
import json,pathlib,urllib.request,shlex,os,time,uuid,fcntl
from e2b import Sandbox
os.environ.update(NO_PROXY='*',no_proxy='*')
c=json.loads(pathlib.Path('/srv/fork2/console.json').read_text())
im=json.loads(pathlib.Path('/srv/fork2/data/registry/python.json').read_text())
opts=dict(api_key=c['key'],api_url=c['api'],sandbox_url='http://127.0.0.1:19611')
def py(s,code):
 r=s.commands.run('exec /usr/local/bin/python3 -c '+shlex.quote(code),user='root',cwd='/',timeout=60)
 assert r.exit_code==0,r.stderr
 return r.stdout.strip()
def request(path):
 r=urllib.request.Request(c['api']+path,data=json.dumps({'timeout':300}).encode(),headers={'X-API-Key':c['key'],'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=120) as f:return json.load(f)
KEEPER="""import os,time,json,hashlib
blob=bytearray(os.urandom(16384));i=0
while True:
 try:
  with open('/tmp/memory-control') as f:blob[0]=int(f.read())
 except FileNotFoundError:pass
 i+=1
 with open('/tmp/memory-report.next','w') as f:json.dump([os.getpid(),i,hashlib.sha256(blob).hexdigest(),blob[0]],f)
 os.replace('/tmp/memory-report.next','/tmp/memory-report.json')
 time.sleep(.05)
"""
def observe(s):
 return json.loads(py(s,"print(open('/tmp/memory-report.json').read())"))
lock=open("/run/skyrl-threeway-benchmark.lock","a");(None if os.environ.get("FORK2_FULL_LOCK_HELD")=="1" else fcntl.flock(lock,fcntl.LOCK_EX))
result=[]
out=pathlib.Path("/home/hong/codex-work/sevenway-fresh-181/fork2/results/live-fork-verified.json")
result=json.load(open(out)) if out.exists() else []
for iteration in range(51):
 if any(r['iteration']==iteration for r in result):continue
 first='parent' if iteration%2 else 'child'
 parent=child=None
 try:
  parent=Sandbox.create(template=im['template_id'],timeout=300,**opts)
  assert py(parent,"import os; f=open('/tmp/isolation','w'); f.write('inherited'); f.flush(); os.fsync(f.fileno()); f.close();print('ok')")=='ok'
  worker=parent.commands.run('exec /usr/local/bin/python3 -c '+shlex.quote(KEEPER),user='root',cwd='/',background=True,timeout=300)
  for _ in range(100):
   try:before=observe(parent);break
   except Exception:time.sleep(.02)
  else:raise RuntimeError('memory worker not ready')
  start_unix_ns=time.time_ns();start=time.perf_counter_ns()
  childid=request('/sandboxes/'+parent.sandbox_id+'/fork')[0]['sandbox']['sandboxID']
  fork_api_ms=(time.perf_counter_ns()-start)/1e6
  child=Sandbox.connect(childid,timeout=300,**opts)
  marker='READY_'+uuid.uuid4().hex;native='NATIVE_'+uuid.uuid4().hex;chunks=[];seen=[];ready=[]
  def got(x):
   chunks.append(x)
   if native+'\n' in ''.join(chunks) and not ready:ready.append(time.perf_counter_ns())
   if marker+'\n' in ''.join(chunks) and not seen:seen.append(time.perf_counter_ns())
  from languages import print_command
  command,_=print_command('python',marker,native)
  r=child.commands.run(command,user='root',cwd='/',timeout=60,on_stdout=got)
  assert r.exit_code==0 and seen and ready
  timing=dict(iteration=iteration,warmup=iteration==0,start_unix_ns=start_unix_ns,parent_id=parent.sandbox_id,child_id=childid,fork_api_ms=fork_api_ms,child_ready_ms=(ready[0]-start)/1e6,child_print_ms=(seen[0]-start)/1e6,ready_definition='child shell native marker received',memory_probe_bytes=16384)
  assert py(child,"print(open('/tmp/isolation').read())")=='inherited'
  inherited=observe(child);assert inherited[0]==before[0] and inherited[2]==before[2]
  for s,value in ((parent,before[3]^1),(child,before[3]^2)):
   py(s,"import os;open('/tmp/memory-control.next','w').write("+repr(str(value))+");os.replace('/tmp/memory-control.next','/tmp/memory-control')")
  for _ in range(100):
   pa,ca=observe(parent),observe(child)
   if pa[2]!=before[2] and ca[2]!=before[2] and pa[2]!=ca[2]:break
   time.sleep(.02)
  else:raise RuntimeError('memory writes not isolated: '+repr(dict(before=before,parent=pa,child=ca)))
  for s,value in ((parent,'parent'),(child,'child')):
   py(s,"import os;f=open('/tmp/isolation','w');f.write("+repr(value)+");f.flush();os.fsync(f.fileno());f.close()")
  assert py(parent,"print(open('/tmp/isolation').read())")=='parent'
  assert py(child,"print(open('/tmp/isolation').read())")=='child'
  # Preserve child VMM traces before lifecycle deletion removes its run directory.
  trace_dir=out.parent/'live-fork-child-traces';trace_dir.mkdir(exist_ok=True)
  import subprocess
  for candidate in pathlib.Path('/run/fork2').glob('**/vmm.log'):
   if childid in str(candidate):
    (trace_dir/f'{iteration:02}-child-vmm.log').write_bytes(candidate.read_bytes())
  if first=='parent':parent.kill();parent=None;survivor=child
  else:child.kill();child=None;survivor=parent
  assert py(survivor,"print(open('/tmp/isolation').read())")==('child' if first=='parent' else 'parent')
  live=observe(survivor);time.sleep(.15);later=observe(survivor)
  assert later[0]==live[0] and later[1]>live[1] and later[2]==live[2]
  try:
   with open(trace_dir/f'{iteration:02}.jsonl','w') as stream:
    subprocess.run(['journalctl','-u','fork2-shared','-u','fork2-runner@*','--since','@'+str(start_unix_ns//10**9),'--grep','VM_FORK stage|export phase sandbox=','-o','json','--no-pager'],stdout=stream,check=False,timeout=10)
  except subprocess.TimeoutExpired:
   timing["trace_collection_timeout"]=True
  result.append({**timing,'memory_inherited':True,'memory_writes_isolated':True,'inherited_process_continued_after_peer_delete':True,'first_deleted':first,'inherited_file':True,'independent_fsync_writes':True,'survivor_exec':True})
 finally:
  for s in (parent,child):
   if s:s.kill()
  out.write_text(json.dumps(result,indent=2))
  print(json.dumps({'iteration':iteration,'completed':len(result)}),flush=True)
print(json.dumps(result,indent=2))
