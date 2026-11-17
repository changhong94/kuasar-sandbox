import os,sys,json,socket,struct,uuid
from pathlib import Path
M=Path('/opt/bench108');sys.path.insert(0,str(M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'));import vm_rpc as v
url='http://127.0.0.1:18887';os.environ.update(E2B_API_KEY=(M/'deploy/fork/api-key').read_text().strip(),E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
from e2b import Sandbox
s=Sandbox.create('base',timeout=120);token=uuid.uuid4().hex;out={}
try:
 path=v.admin(M/'deploy/fork/admin.sock','sandbox-get',sandbox_id=s.sandbox_id)['live_fork']['vsock_socket']
 def rpc(payload, method="ForkControl"):
  request=v.blob(1,'grpc.SandboxService')+v.blob(2,method)+v.blob(3,payload)+v.integer(4,15_000_000_000)
  with socket.socket(socket.AF_UNIX) as sock:
   sock.settimeout(20);sock.connect(path);sock.sendall(b'CONNECT 1024\n');line=b''
   while not line.endswith(b'\n'):line+=v.exact(sock,1)
   assert line.startswith(b'OK ');sock.sendall(struct.pack('>IIBB',len(request),1,1,0)+request);n,stream,kind,flags=struct.unpack('>IIBB',v.exact(sock,10));assert stream==1 and kind==2;reply=v.fields(v.exact(sock,n))
  status=v.fields(reply.get(1,b''));return status.get(1,0),status.get(2,b'').decode(),v.fields(reply.get(2,b''))
 freeze=v.blob(1,token);assert rpc(freeze)[0]==0
 wrong=rpc(v.blob(1,'wrong-owner')+v.integer(2,1)+v.blob(6,b'x'*32));assert wrong[0]!=0;out['wrong_owner_rejected']=True
 invalid=rpc(freeze+v.integer(2,1)+v.blob(3,'02:00:00:00:00:ff')+v.blob(6,b'x'*32));assert invalid[0]!=0;out['invalid_network_rejected']=True
 denied=rpc(b'', 'SetupSandbox');assert denied[0]!=0 and 'frozen' in denied[1].lower(),denied
 out['lifecycle_gate_remained_closed_after_failure']=True
 good=rpc(freeze+v.integer(2,1)+v.blob(6,os.urandom(32)));assert good[0]==0 and good[2].get(2)==1
 released=rpc(b'', 'SetupSandbox');assert 'frozen' not in released[1].lower()
 assert v.execute(path,['/bin/busybox','true'])['exit_code']==0;out['owner_can_recover']=True
finally:s.kill()
(M/'results/five-rounds-108/round4/gate-validation.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
