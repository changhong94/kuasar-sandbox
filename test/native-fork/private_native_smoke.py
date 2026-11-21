#!/usr/bin/env python3
"""Direct inherited-RAM fork with independent sandbox-ctl owner processes.

Timing starts before spawning the fork request command and ends after its
completion (including parent reattach), then after a fresh Python print reaches
this client. All source/child services are isolated and explicitly owned here.
"""
import argparse,json,shutil,os,pathlib,selectors,signal,subprocess,time,uuid,statistics
p=argparse.ArgumentParser()
for name in ('cli','ch','config','work'):p.add_argument('--'+name,required=True)
p.add_argument('--count',type=int,default=1)
p.add_argument('--network',action='store_true')
a=p.parse_args()
work=pathlib.Path(a.work);work.mkdir(parents=True,exist_ok=False)
run=pathlib.Path('/run')/('kn-private-'+uuid.uuid4().hex[:8]);run.mkdir(mode=0o700)
cfg=json.loads(pathlib.Path(a.config).read_text());parent_cfg=work/'parent.json';parent_cfg.write_text(json.dumps(cfg))
child_cfg=work/'child.json';child_cfg.write_text(json.dumps({'resources':cfg['resources'],'boot':{'runtime':cfg['boot']['runtime']}}))
owners={};samples=[]
if a.network:
 assert os.stat('/proc/self/ns/net').st_ino!=os.stat('/proc/1/ns/net').st_ino,'private network namespace required'
 for j in range(3):
  name=f'knpriv{j}'
  for args in (['ip','tuntap','add','dev',name,'mode','tap'],['ip','addr','add',f'198.18.249.{1+4*j}/30','dev',name],['ip','link','set',name,'up']):subprocess.run(args,check=True)
def network_config(index):
 return {'tap':f'knpriv{index}','interface':'eth0','ip':f'198.18.249.{2+4*index}/30','mac':f'02:ab:00:00:00:{index+1:02x}','hostname':f'private-{index}'}
def start(sid,parent=None,cid=41701):
 if a.network:
  index=0 if parent is None else (2 if sid.startswith('g') else 1)
  selected=json.loads((child_cfg if parent else parent_cfg).read_text());selected['network']=network_config(index)
  (child_cfg if parent else parent_cfg).write_text(json.dumps(selected))
 r,w=os.pipe();args=[a.cli,'fork' if parent else 'run','--config',str(child_cfg if parent else parent_cfg),'--sandbox-id',sid,'--run-root',str(run),'--base-root',str(work/'base'),'--ch-binary',a.ch,'--ready-fd',str(w),'--enable-checkpoint']
 if parent:args+=['--parent-id',parent,'--backend','native-private','--child-cid',str(cid)]
 else:args+=['--private-ram-fork','--console','off']
 logpath=work/(sid+'.log');log=logpath.open('wb');begin=time.monotonic_ns()
 proc=subprocess.Popen(args,stdout=log,stderr=log,pass_fds=(w,));owners[sid]=(proc,log);os.close(w)
 sel=selectors.DefaultSelector();sel.register(r,selectors.EVENT_READ);data=b'';deadline=time.monotonic()+60
 try:
  while time.monotonic()<deadline:
   if proc.poll() is not None:raise RuntimeError(logpath.read_text()[-12000:])
   if sel.select(.05):
    chunk=os.read(r,65536)
    if not chunk:raise RuntimeError('readiness closed: '+logpath.read_text()[-12000:])
    data+=chunk
    if b'ready' in data.splitlines():break
  else:raise TimeoutError('readiness: '+sid)
  ready=time.monotonic_ns();internal=None
  if parent:
   while time.monotonic()<deadline:
    records=[line for line in logpath.read_text().splitlines() if line.startswith('fork_result=')]
    if records:
     internal=json.loads(records[-1].split('=',1)[1]);assert 'error' not in internal,internal;break
    if proc.poll() is not None:raise RuntimeError(logpath.read_text()[-12000:])
    time.sleep(.001)
   else:raise TimeoutError('fork completion: '+sid)
  return begin,ready,time.monotonic_ns(),internal
 finally:sel.close();os.close(r)
def execute(sid,program):
 result=subprocess.run([a.cli,'exec','--sandbox-id',sid,'--run-root',str(run),'--','/usr/local/bin/python3','-c',program],capture_output=True,text=True,timeout=15)
 if result.returncode:raise RuntimeError(f'{sid}: {result.stdout} {result.stderr}')
 return result.stdout.strip()
def stop(sid):
 proc,log=owners.pop(sid)
 if proc.poll() is None:proc.send_signal(signal.SIGTERM)
 try:
  code=proc.wait(timeout=15)
  if code!=0:raise RuntimeError(f'{sid}: owner exit={code}')
 except subprocess.TimeoutExpired:proc.kill();proc.wait();raise
 finally:log.close()
try:
 for i in range(a.count):
  parent=f'p{i}';child=f'c{i}';grand=f'g{i}';start(parent)
  token=uuid.uuid4().hex
  assert execute(parent,"import sqlite3; d=sqlite3.connect('/root/state.db'); d.execute('PRAGMA synchronous=FULL'); d.execute('CREATE TABLE t(v)'); d.execute('INSERT INTO t VALUES (73)'); d.commit(); print('stored')")=='stored'
  worker="import os,time; n=0\nwhile True:\n n+=1; open('/root/tick.tmp','w').write(str(n)); os.replace('/root/tick.tmp','/root/tick'); time.sleep(.01)"
  pid=int(execute(parent,"import subprocess; p=subprocess.Popen(['/usr/local/bin/python3','-c',"+repr(worker)+"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True); print(p.pid)"))
  begin,ready,complete,internal=start(child,parent,41701+i*2)
  assert execute(child,f"print({token!r},flush=True)")==token
  printed=time.monotonic_ns()
  if a.network:
   import socket,threading
   for target,index in ((parent,0),(child,1)):
    server=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);server.bind((f'198.18.249.{1+4*index}',0));server.settimeout(5)
    seen=[]
    def echo():
     data,addr=server.recvfrom(4096);seen.append(addr[0]);server.sendto(data,addr)
    thread=threading.Thread(target=echo);thread.start()
    text=execute(target,"import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(5); s.sendto(b'isolated',"+repr(server.getsockname())+"); print(s.recv(4096).decode())")
    thread.join(6);server.close();assert text=='isolated' and seen==[f'198.18.249.{2+4*index}'],seen
  get="import sqlite3; d=sqlite3.connect('/root/state.db'); print(d.execute('SELECT v FROM t').fetchone()[0])"
  assert execute(child,get)=='73'
  tick=f"import os; os.kill({pid},0); print(open('/root/tick').read())"
  before=int(execute(parent,tick));assert int(execute(child,tick))>0
  assert execute(child,f"import os,signal; os.kill({pid},signal.SIGTERM); print('stopped')")=='stopped'
  assert int(execute(parent,tick))>before
  assert execute(child,"import sqlite3; d=sqlite3.connect('/root/state.db'); d.execute('PRAGMA synchronous=FULL'); d.execute('UPDATE t SET v=91'); d.commit(); print('written')")=='written'
  assert execute(parent,get)=='73'
  # Record shared immutable carriers before deleting source-owned paths.
  carriers=[]
  for path in (work/'base'/child).rglob('*.image'):
   stat=path.stat();carriers.append({'path':str(path.relative_to(work)), 'inode':stat.st_ino,'links':stat.st_nlink,'bytes':stat.st_size})
  stop(parent) # Parent owner process is gone, not merely its VM.
  shutil.rmtree(work/'base'/parent)
  assert execute(child,get)=='91'
  start(grand,child,41702+i*2);assert execute(grand,get)=='91';stop(grand)
  assert execute(child,"print('survived')")=='survived';stop(child)
  sample={'iteration':i,'request_to_child_ready_ms':(ready-begin)/1e6,'request_to_complete_ms':(complete-begin)/1e6,'request_to_print_ms':(printed-begin)/1e6,'internal':internal,'independent_owners':True,'inherited_process':True,'sqlite_full_cow':True,'both_destruction_orders':True,'parent_directory_deleted':True,'independent_network':a.network,'image_carriers':carriers}
  samples.append(sample);(work/'samples.json').write_text(json.dumps(samples,indent=2));print(json.dumps(sample),flush=True)
 assert not list(run.iterdir()),list(run.iterdir())
 summary={k:{'median':statistics.median(s[k] for s in samples),'max':max(s[k] for s in samples)} for k in ('request_to_child_ready_ms','request_to_complete_ms','request_to_print_ms')}
 (work/'result.json').write_text(json.dumps({'samples':samples,'summary':summary},indent=2));print(json.dumps(summary),flush=True)
finally:
 for sid in list(owners):
  try:stop(sid)
  except Exception as e:print('cleanup:',sid,e,flush=True)
 if run.exists() and not list(run.iterdir()):run.rmdir()
