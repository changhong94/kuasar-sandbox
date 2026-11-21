#!/usr/bin/python3
"""Runs only inside the isolated nested host; checkpoints survive its hard reset."""
import json,os,pathlib,selectors,signal,socket,subprocess,time,uuid,traceback
assert pathlib.Path('/native-nested-host').exists()
root=pathlib.Path('/data');root.mkdir(exist_ok=True);run='/run/test';os.makedirs(run,exist_ok=True)
bin=pathlib.Path('/tools');owners={}
def command(args):
 p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=180)
 if p.returncode:raise RuntimeError(str(args[:3])+': '+p.stderr[-6000:])
 return p.stdout.strip()
def persist(path,value):
 with open(path,'w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
 fd=os.open(str(path.parent),os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def py(sid,code):return command([bin/'sandbox-ctl','exec','--sandbox-id',sid,'--run-root',run,'--','/usr/local/bin/python3','-c',code])
def start(sid,parent=None,restore=None):
 cfg='/parent.json' if not parent and not restore else '/child.json'
 r,w=os.pipe();args=[bin/'sandbox-ctl','fork' if parent else 'run','--config',cfg,'--sandbox-id',sid,'--run-root',run,'--base-root','/data/base','--ch-binary',bin/'cloud-hypervisor','--ready-fd',str(w),'--enable-checkpoint','--manifest-config','/manifest.json']
 if parent:args+=['--parent-id',parent,'--backend','native-private','--child-cid','41702']
 elif restore:args+=['--restore',restore]
 else:args+=['--private-ram-fork','--console','off']
 log=(root/(sid+'.log')).open('wb');proc=subprocess.Popen(list(map(str,args)),stdout=log,stderr=log,pass_fds=(w,));owners[sid]=(proc,log);os.close(w)
 sel=selectors.DefaultSelector();sel.register(r,selectors.EVENT_READ);buf=b''
 try:
  deadline=time.monotonic()+90
  while time.monotonic()<deadline:
   if sel.select(.1):
    data=os.read(r,65536)
    if not data:raise RuntimeError((root/(sid+'.log')).read_text()[-8000:])
    buf+=data
    if b'ready' in buf.splitlines():return
  raise TimeoutError(sid)
 finally:os.close(r);sel.close()
def stop(sid):
 p,f=owners.pop(sid);p.send_signal(signal.SIGTERM);assert p.wait(timeout=30)==0;f.close()
try:
 os.environ['MANIFEST_KEY']=pathlib.Path('/manifest-key').read_text().strip()
 if not (root/'store').exists():command([bin/'store-ctl','init','--config','/store.json','--generation','G1'])
 log=(root/'store.log').open('ab');store=subprocess.Popen([str(bin/'store-ctl'),'serve','--config','/store.json'],stdout=log,stderr=log)
 for _ in range(100):
  try:
   with socket.create_connection(('127.0.0.1',19331),.1):break
  except OSError:time.sleep(.05)
 if not (root/'plan.json').exists():
  start('parent')
  worker="import os,time; n=0\nwhile True:\n n+=1; open('/root/tick.next','w').write(str(n)); os.replace('/root/tick.next','/root/tick'); time.sleep(.01)"
  pid=int(py('parent',"import subprocess; p=subprocess.Popen(['/usr/local/bin/python3','-c',"+repr(worker)+"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True); print(p.pid)"))
  py('parent',"import sqlite3; d=sqlite3.connect('/root/state.db'); d.execute('PRAGMA synchronous=FULL'); d.execute('CREATE TABLE t(v)'); d.execute('INSERT INTO t VALUES (73)'); d.commit()")
  start('child','parent')
  py('child',"import sqlite3; d=sqlite3.connect('/root/state.db'); d.execute('PRAGMA synchronous=FULL'); d.execute('UPDATE t SET v=91'); d.commit()")
  snapshots=[]
  for mode in ('local','remote'):
   for sid,value in (('parent',73),('child',91)):
    args=[bin/'sandbox-ctl','snapshot','--sandbox-id',sid,'--run-root',run,'--resume','--json']
    args+=['--upload'] if mode=='remote' else ['--output',root/(mode+'-'+sid)]
    result=json.loads(command(args));snapshots.append(dict(mode=mode,source=sid,value=value,pid=pid,capture=result))
  persist(root/'plan.json',snapshots)
  # The plan itself is synced; all artifact durability must come from publish.
  print('NESTED_DURABLE_READY',flush=True)
  while True:time.sleep(1)
 else:
  records=json.loads((root/'plan.json').read_text());results=[]
  print('NESTED_AFTER_RESET',flush=True)
  for mode in ('local','remote'):
   for r in [x for x in records if x['mode']==mode]:
    sid=mode+'-'+r['source'];cap=r['capture'];ref=cap['snapshotRef']
    if mode=='local':ref='file://'+str(root/(mode+'-'+r['source']))+'/'+ref.removeprefix('file://')
    start(sid,restore=ref)
    value=py(sid,"import sqlite3; d=sqlite3.connect('/root/state.db'); print(d.execute('SELECT v FROM t').fetchone()[0])")
    assert value==str(r['value']),(sid,value)
    code=f"import os; os.kill({r['pid']},0); print(open('/root/tick').read())"
    before=int(py(sid,code));time.sleep(.05);assert int(py(sid,code))>before
   p=mode+'-parent';c=mode+'-child'
   py(c,"import sqlite3; d=sqlite3.connect('/root/state.db'); d.execute('PRAGMA synchronous=FULL'); d.execute('UPDATE t SET v=99'); d.commit()")
   assert py(p,"import sqlite3; print(sqlite3.connect('/root/state.db').execute('SELECT v FROM t').fetchone()[0])")=='73'
   stop(p);assert py(c,"print('independent')")=='independent';stop(c)
   results.append(dict(mode=mode,process_resumed=True,sqlite_durable=True,independent_write_and_destroy=True))
  persist(root/'verified.json',results);print('NESTED_VERIFIED '+json.dumps(results),flush=True)
  while True:time.sleep(1)
except BaseException:
 traceback.print_exc();print('NESTED_FAILED',flush=True)
 while True:time.sleep(1)
