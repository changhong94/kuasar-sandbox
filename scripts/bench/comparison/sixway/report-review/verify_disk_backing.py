"""Real guest persistent backing and live-fork independence; outside timing."""
import fcntl,json,socket,http.client,sys,uuid
from pathlib import Path
B=Path('/home/hong/src/research/report-review-113')
Q=Path('/home/hong/src/research/python-latest-113/src/kuasar-fork/kuasar-io/kuasar')
sys.path[:0]=[str(B),str(B/'tools'),str(Q/'integrations/e2b')]
import live_fork as live
import vm_rpc
from languages import select_language
from startup import setup
from pool_gate import wait
class UnixHTTP(http.client.HTTPConnection):
 def connect(self):
  self.sock=socket.socket(socket.AF_UNIX);self.sock.settimeout(30);self.sock.connect(self.host)
def backing(s):
 info=vm_rpc.admin(live.DEPLOY/'admin.sock','sandbox-get',sandbox_id=s.sandbox_id)
 client=UnixHTTP(info['live_fork']['api_socket'])
 try:
  client.request('GET','/api/v1/vm.info');r=client.getresponse();assert r.status==200
  config=json.loads(r.read())['config']
 finally:client.close()
 disks=[d for d in config['disks'] if d.get('serial')=='app-write']
 assert len(disks)==1 and not disks[0].get('readonly',False),disks
 path=Path(disks[0]['path'])
 with path.open('rb') as f:assert f.read(4)==b'QFI\xfb'
 root=vm_rpc.execute(info['live_fork']['vsock_socket'],['/bin/busybox','cat','/proc/self/mountinfo'])
 assert root['exit_code']==0,root['stderr']
 mounts=root['stdout'].decode()+'\n'+live.command(s,'cat /proc/self/mountinfo')
 ext4=[line for line in mounts.splitlines() if '/run/image-writes' in line and ' - ext4 ' in line]
 overlay=[line for line in mounts.splitlines() if 'upperdir=/run/image-writes/upper' in line]
 assert ext4 and overlay,mounts
 return {'writable_disk_path':str(path),'qcow2_header_verified':True,'ext4_mount':ext4,'overlay_mount':overlay}
cfg=select_language(json.loads((B/'tools/config.json').read_text()),'python')
c,Sandbox=setup('kuasar-fork',cfg);owned={};rows=[];pending=[]
def save(): (B/'disk-backing-verification.json').write_text(json.dumps({'rows':rows,'owned':list(owned),'pending':pending},indent=2))
def delete(s):s.kill();owned.pop(s.sandbox_id);save()
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  for order in ('parent-first','child-first'):
   wait(c,64,600)
   row={'order':order,'success':False};rows.append(row);save()
   parent=Sandbox.create(c['template'],timeout=600,request_timeout=180);owned[parent.sandbox_id]=parent;save()
   marker=uuid.uuid4().hex
   parent.files.write('/tmp/durable-proof',marker,user='root');live.command(parent,'sync /tmp/durable-proof')
   live.network_ready(c,parent.sandbox_id)
   response=live.request(c,'/sandboxes/'+parent.sandbox_id+'/fork',{'count':1,'timeout':600})
   cid=response[0]['sandbox']['sandboxID'];pending.append(cid);save()
   child=Sandbox.connect(cid,timeout=600,request_timeout=180);owned[cid]=child;pending.remove(cid);save()
   row['parent']=backing(parent);row['child']=backing(child)
   assert row['parent']['writable_disk_path']!=row['child']['writable_disk_path']
   assert child.files.read('/tmp/durable-proof',user='root')==marker
   for s,value in ((parent,'parent-'+marker),(child,'child-'+marker)):
    s.files.write('/tmp/durable-proof',value,user='root');live.command(s,'sync /tmp/durable-proof')
   assert parent.files.read('/tmp/durable-proof',user='root')=='parent-'+marker
   assert child.files.read('/tmp/durable-proof',user='root')=='child-'+marker
   first,last=(parent,child) if order=='parent-first' else (child,parent)
   expected=('child-' if order=='parent-first' else 'parent-')+marker
   delete(first)
   assert live.command(last,"/usr/local/bin/python3 -c 'print(\"alive\",flush=True)'")=='alive'
   assert last.files.read('/tmp/durable-proof',user='root')==expected
   delete(last);row['success']=True;save();wait(c,64,600)
 finally:
  for s in list(owned.values()):delete(s)
  for sid in list(pending):
   Sandbox.kill(sid);pending.remove(sid);save()
assert all(r['success'] for r in rows)
print('PASS durable ext4/QCOW2 backing, independent live forks and both deletion orders')
