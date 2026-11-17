import os,sys,json,time,shlex,uuid
from pathlib import Path
M=Path('/opt/bench108');sys.path.insert(0,str(M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'));import vm_rpc
key=(M/'deploy/fork/api-key').read_text().strip();url='http://127.0.0.1:18887'
os.environ.update(E2B_API_KEY=key,E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
from e2b import Sandbox
owned=[];report={}
def run(s,c):
 r=s.commands.run(c,user='root',timeout=20);assert r.exit_code==0,(c,r.stderr);return r.stdout.strip()
def raw(s,cmd):
 info=vm_rpc.admin(M/'deploy/fork/admin.sock','sandbox-get',sandbox_id=s.sandbox_id)['live_fork']
 z=vm_rpc.execute(info['vsock_socket'],['/bin/sh','-c',cmd]);assert z['exit_code']==0,z;return z['stdout'].decode(),info
try:
 a=Sandbox.create('base',timeout=120);owned.append(a)
 b=Sandbox.create('base',timeout=120);owned.append(b)
 infos=[];addresses=[];macs=[];maps=[]
 for s in (a,b):
  text,info=raw(s,'/bin/busybox ip -o -4 addr show; /bin/busybox ip -o link show')
  infos.append(info);addresses.append(next(line.split(' inet ')[1].split('/')[0] for line in text.splitlines() if ' inet ' in line and '127.0.0.1/' not in line));macs.append(text.split('link/ether ')[1].split()[0])
  maptext=Path('/proc/'+str(info['pid'])+'/maps').read_text()
  backed=[line for line in maptext.splitlines() if 'memory-ranges' in line]
  assert backed and all(line.split()[1]=='rw-p' for line in backed),backed
  maps.append(backed)
 assert addresses[0]!=addresses[1] and macs[0]!=macs[1] and infos[0]['cid']!=infos[1]['cid']
 markers=[uuid.uuid4().hex,uuid.uuid4().hex]
 for s,mark in zip((a,b),markers):
  run(s,'printf '+mark+' > /tmp/network-marker; nohup python3 -m http.server 18080 --bind 0.0.0.0 --directory /tmp >/tmp/http.log 2>&1 </dev/null &')
 def fetch(s,ip):
  cmd="import urllib.request;print(urllib.request.urlopen('http://"+ip+":18080/network-marker',timeout=3).read().decode())"
  return run(s,'python3 -c '+shlex.quote(cmd))
 for _ in range(50):
  try:
   assert fetch(a,addresses[1])==markers[1] and fetch(b,addresses[0])==markers[0];break
  except Exception:time.sleep(.05)
 else:raise RuntimeError('independent network communication failed')
 a.kill();owned.remove(a)
 assert fetch(b,addresses[1])==markers[1]
 report=dict(success=True,ips=addresses,macs=macs,cids=[i['cid'] for i in infos],private_file_maps=maps,mutual_http=True,survivor_after_peer_destroy=True)
finally:
 for s in owned:s.kill()
 (M/'results/python-opt-108/network-validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
