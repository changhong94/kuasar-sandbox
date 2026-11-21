#!/usr/bin/env python3
"""Validate only objects created by this test through the new console API."""
import argparse,json,pathlib,subprocess,time,urllib.request,uuid
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--leave-example',action='store_true');a=p.parse_args()
base='http://127.0.0.1:18089';owned=[];snaps=[];results=[]
def req(path,body=None):
 r=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=15) as f:return json.load(f)
def awaitrow(kind,ident,want='running',timeout=240):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  rows=req('/api/state')[kind];row=next((r for r in rows if r['id']==ident),None)
  if want=='deleted' and row is None:return
  if row and row['state']==want and not row.get('busy'):return row
  if row and row['state']=='failed':raise RuntimeError(json.dumps(row))
  time.sleep(.2)
 raise TimeoutError(ident)
def create(kind,ident):
 row=req('/api/create',{'kind':kind,'source':ident});owned.append(row['id']);return awaitrow('sandboxes',row['id'])
def py(row,code):
 p=subprocess.run(['/srv/forklab-native/bin/sandbox-ctl','exec','--sandbox-id',row['runtime_id'],'--run-root','/run/forklab-native/sandboxes','--','python3','-c',code],capture_output=True,text=True,timeout=30)
 if p.returncode:raise RuntimeError(p.stderr[-3000:])
 return p.stdout.strip()
def delete(row):
 req('/api/action',{'id':row['id'],'action':'destroy'});awaitrow('sandboxes',row['id'],'deleted');owned.remove(row['id'])
try:
 end=time.monotonic()+600
 while True:
  images=req('/api/state')['images']
  if len(images)==5 and all(i['state']=='ready' for i in images):break
  if any(i['state']=='failed' for i in images):raise RuntimeError(str([(i['id'],i.get('error')) for i in images]))
  if time.monotonic()>end:raise TimeoutError('image imports')
  time.sleep(2)
 for image in images:
  parent=create('image',image['id']);token=uuid.uuid4().hex
  assert py(parent,"print("+repr(token)+",flush=True)")==token
  py(parent,"open('/root/native-proof','w').write('captured')")
  worker="import os,time; n=0\nwhile True:\n n+=1; open('/root/tick-next','w').write(str(n)); os.replace('/root/tick-next','/root/tick'); time.sleep(.01)"
  pid=int(py(parent,"import subprocess,sys; p=subprocess.Popen([sys.executable,'-c',"+repr(worker)+"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True); print(p.pid)"))
  snap=req('/api/snapshot',{'sandbox_id':parent['id']});snaps.append(snap['id']);snap=awaitrow('snapshots',snap['id'],'ready')
  assert snap['pause_ms']>0 and snap['durable_ms']>=snap['pause_ms']
  child=create('snapshot',snap['id']);assert py(child,"print(open('/root/native-proof').read())")=='captured'
  tick=f"import os; os.kill({pid},0); print(open('/root/tick').read())"
  for row in (parent,child):
   first=int(py(row,tick));time.sleep(.05);assert int(py(row,tick))>first
  py(parent,"open('/root/native-proof','w').write('parent')");py(child,"open('/root/native-proof','w').write('child')")
  assert py(parent,"print(open('/root/native-proof').read())")=='parent'
  delete(parent);assert py(child,"print(open('/root/native-proof').read())")=='child'
  again=create('snapshot',snap['id']);assert py(again,"print(open('/root/native-proof').read())")=='captured';delete(again)
  # Removing the template must not invalidate an already restored child.
  req('/api/delete-snapshot',{'id':snap['id']});snaps.remove(snap['id']);assert py(child,"print(open('/root/native-proof').read())")=='child';delete(child)
  result={'image':image['name'],'digest':image['manifest'],'pause_ms':snap['pause_ms'],'durable_ms':snap['durable_ms'],'python_print':True,'inherited_process':True,'source_delete_snapshot_reuse':True,'snapshot_delete_child_survives':True,'independent_destroy':True};results.append(result);print(json.dumps(result),flush=True)
 if a.leave_example:
  parent=create('image','python');py(parent,"open('/root/demo.txt','w').write('native snapshot demo')")
  snap=req('/api/snapshot',{'sandbox_id':parent['id']});snaps.append(snap['id']);snap=awaitrow('snapshots',snap['id'],'ready');owned.remove(parent['id']);snaps.remove(snap['id'])
 report={'passed':True,'results':results,'example':{'sandbox':parent['id'],'snapshot':snap['id']} if a.leave_example else None}
 pathlib.Path(a.output).write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
finally:
 for ident in owned:
  try:req('/api/action',{'id':ident,'action':'destroy'})
  except Exception as e:print('cleanup failed',ident,str(e),flush=True)
 for ident in snaps:
  try:req('/api/delete-snapshot',{'id':ident})
  except Exception as e:print('cleanup failed',ident,str(e),flush=True)
