import fcntl,json,sys,time,uuid,urllib.request
from pathlib import Path
B=Path('/home/hong/src/research/report-revision-113')
sys.path.insert(0,'/home/hong/src/research/startup-modes-113')
import live_fork as live
from languages import select_language
from startup import setup
cfg=select_language(json.loads((live.TOOLS/'config.json').read_text()),'python')
c,Sandbox=setup('kuasar-fork',cfg)
results=[];owned={};pending=[]
def save(): (B/'manifest-guest-validation.json').write_text(json.dumps({'rows':results,'owned':list(owned),'pending':pending},indent=2))
def delete(s):s.kill();owned.pop(s.sandbox_id);save()
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  for order in ['parent-first','child-first']:
   row={'order':order,'success':False};results.append(row);save()
   response=live.request(c,'/sandboxes',{'templateID':c['template'],'timeout':600,'snapshotMode':'manifest'})
   sid=response['sandboxID'];pending.append(sid);save()
   parent=Sandbox.connect(sid,timeout=600,request_timeout=180);owned[sid]=parent;pending.remove(sid);save()
   row['parent']=sid
   marker=uuid.uuid4().hex
   assert live.command(parent,"/usr/local/bin/python3 -c 'print(\""+marker+"\",flush=True)'")==marker
   parent.files.write('/tmp/live-progress',(live.BASE/'progress').read_bytes(),user='root')
   live.command(parent,'chmod 700 /tmp/live-progress; nohup /tmp/live-progress >/tmp/live-progress.log 2>/tmp/live-progress.err </dev/null &')
   parent.files.write('/tmp/remote-proof',b'persisted-parent',user='root')
   live.command(parent,'sync /tmp/remote-proof');live.network_ready(c,sid);time.sleep(.05)
   before=live.progress(parent)[-1]
   response=live.request(c,'/sandboxes/'+sid+'/fork',{'count':1,'timeout':600})
   cid=response[0]['sandbox']['sandboxID'];pending.append(cid);save()
   child=Sandbox.connect(cid,timeout=600,request_timeout=180);owned[cid]=child;pending.remove(cid);row['child']=cid;save()
   assert child.files.read('/tmp/remote-proof',format='bytes',user='root')==b'persisted-parent'
   child.files.write('/tmp/remote-proof',b'child-only',user='root');live.command(child,'sync /tmp/remote-proof')
   assert parent.files.read('/tmp/remote-proof',format='bytes',user='root')==b'persisted-parent'
   assert live.progress(parent)[-1][1]>before[1] and live.progress(child)[-1][1]>before[1]
   first,last=(parent,child) if order=='parent-first' else (child,parent)
   delete(first)
   assert live.command(last,"/usr/local/bin/python3 -c 'print(\""+marker+"\",flush=True)'")==marker
   assert live.progress(last)[-1][1]>before[1]
   delete(last)
   row.update(success=True,process_inherited=True,files_independent=True,survives_peer_destroy=True);save()
 finally:
  for s in list(owned.values()):
   try:delete(s)
   except Exception as error:results.append({'cleanup_error':repr(error),'sid':s.sandbox_id});save()
  for sid in list(pending):
   req=urllib.request.Request(c['api_url']+'/sandboxes/'+sid,method='DELETE',headers={'X-API-Key':Path(c['key_file']).read_text().strip()})
   with urllib.request.urlopen(req,timeout=180):pass
   pending.remove(sid);save()
print('PASS remote templates, live fork, both destruction orders')
