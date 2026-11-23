#!/usr/bin/env python3
"""Independent fork2 only: inherited disk, independent mutation and deletion."""
import json,pathlib,urllib.request,shlex,os,time
from e2b import Sandbox
os.environ.update(NO_PROXY='*',no_proxy='*')
c=json.loads(pathlib.Path('/srv/fork2/console.json').read_text())
im=json.loads(pathlib.Path('/srv/fork2/data/registry/python.json').read_text())
opts=dict(api_key=c['key'],api_url=c['api'],sandbox_url='http://127.0.0.1:19211')
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
 with open('/tmp/memory-report.next','w') as f:json.dump([os.getpid(),i,hashlib.sha256(blob).hexdigest()],f)
 os.replace('/tmp/memory-report.next','/tmp/memory-report.json')
 time.sleep(.05)
"""
def observe(s):
 return json.loads(py(s,"print(open('/tmp/memory-report.json').read())"))
result=[]
for first in ('parent','child'):
 parent=child=None
 try:
  parent=Sandbox.create(template=im['template_id'],timeout=300,**opts)
  assert py(parent,"import os; f=open('/tmp/isolation','w'); f.write('inherited'); f.flush(); os.fsync(f.fileno()); f.close();print('ok')")=='ok'
  worker=parent.commands.run('exec /usr/local/bin/python3 -c '+shlex.quote(KEEPER),user='root',cwd='/',background=True,timeout=300)
  for _ in range(100):
   try:before=observe(parent);break
   except Exception:time.sleep(.02)
  else:raise RuntimeError('memory worker not ready')
  childid=request('/sandboxes/'+parent.sandbox_id+'/fork')[0]['sandbox']['sandboxID']
  child=Sandbox.connect(childid,timeout=300,**opts)
  assert py(child,"print(open('/tmp/isolation').read())")=='inherited'
  inherited=observe(child);assert inherited[0]==before[0] and inherited[2]==before[2]
  for s,value in ((parent,1),(child,2)):
   py(s,"open('/tmp/memory-control','w').write("+repr(str(value))+")")
  for _ in range(100):
   pa,ca=observe(parent),observe(child)
   if pa[2]!=before[2] and ca[2]!=before[2] and pa[2]!=ca[2]:break
   time.sleep(.02)
  else:raise RuntimeError('memory writes not isolated')
  for s,value in ((parent,'parent'),(child,'child')):
   py(s,"import os;f=open('/tmp/isolation','w');f.write("+repr(value)+");f.flush();os.fsync(f.fileno());f.close()")
  assert py(parent,"print(open('/tmp/isolation').read())")=='parent'
  assert py(child,"print(open('/tmp/isolation').read())")=='child'
  if first=='parent':parent.kill();parent=None;survivor=child
  else:child.kill();child=None;survivor=parent
  assert py(survivor,"print(open('/tmp/isolation').read())")==('child' if first=='parent' else 'parent')
  live=observe(survivor);time.sleep(.15);later=observe(survivor)
  assert later[0]==live[0] and later[1]>live[1] and later[2]==live[2]
  result.append({'memory_inherited':True,'memory_writes_isolated':True,'inherited_process_continued_after_peer_delete':True,'first_deleted':first,'inherited_file':True,'independent_fsync_writes':True,'survivor_exec':True})
 finally:
  for s in (parent,child):
   if s:s.kill()
print(json.dumps(result,indent=2))
