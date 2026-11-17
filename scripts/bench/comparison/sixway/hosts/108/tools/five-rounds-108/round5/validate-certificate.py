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
 freeze=v.blob(1,token)
 prepared=rpc(freeze+v.integer(7,1));assert prepared[0]==0 and prepared[2].get(4)==1,prepared
 out['empty_template_certified']=True
 denied=rpc(v.blob(1,'/bin/true'), 'ExecVMProcess');assert denied[0]!=0 and 'frozen' in denied[1],denied
 out['exec_blocked_while_certified']=True
 wrong=rpc(v.blob(1,'wrong-owner')+v.integer(2,1));assert wrong[0]!=0,wrong
 good=rpc(freeze+v.integer(2,1)+v.blob(6,os.urandom(32)));assert good[0]==0,good
 assert v.execute(path,['/bin/busybox','true'])['exit_code']==0
 out['source_thaws_and_exec_recovers']=True
 descriptors=v.execute(path,['/bin/busybox','sh','-c','for f in /proc/1/fd/*; do /bin/busybox readlink "$f"; done'])
 assert b'freezer.state' not in descriptors['stdout'],descriptors
 out['certificate_fd_closed_after_release']=True
 # A listener alone must invalidate certification, even without connections.
 import shlex,time
 code="import socket,time; s=socket.socket(); s.bind(('127.0.0.1',34567)); s.listen(); open('/tmp/cert-listener-ready','w').close(); time.sleep(120)"
 z=s.commands.run('nohup python3 -c '+shlex.quote(code)+' >/tmp/cert-listener.log 2>&1 </dev/null &',user='root');assert z.exit_code==0
 for _ in range(100):
  if s.commands.run('test -f /tmp/cert-listener-ready && echo yes || true',user='root').stdout.strip()=='yes':break
  time.sleep(.01)
 token=uuid.uuid4().hex;freeze=v.blob(1,token)
 prepared=rpc(freeze+v.integer(7,1));assert prepared[0]==0 and not prepared[2].get(4),prepared
 out['listener_template_falls_back']=True
 assert v.execute(path,['/bin/busybox','true'])['exit_code']==0
 out['fallback_thaws_workload']=True
 mac=v.execute(path,['/bin/busybox','cat','/sys/class/net/eth0/address'])['stdout'].decode().strip()
 interface=v.blob(2,'eth0')+v.integer(4,1500)+v.blob(5,mac)
 forced=rpc(freeze+v.integer(2,1)+v.blob(3,mac)+v.blob(4,interface)+v.blob(6,os.urandom(32))+v.integer(8,1))
 assert forced[0]==0 and not forced[2].get(5),forced
 out['skip_request_without_guest_certificate_runs_cleanup']=True

finally:s.kill()
(M/'results/five-rounds-108/round5/certificate-validation.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
