import os,sys,json,time,shlex,urllib.request
from pathlib import Path
M=Path('/opt/bench108'); key=(M/'deploy/fork/api-key').read_text().strip();url='http://127.0.0.1:18887'
os.environ.update(E2B_API_KEY=key,E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
from e2b import Sandbox
code='''import socket,json,os,time,uuid
listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
def pair():
 a=socket.create_connection(listener.getsockname(),timeout=1);b,_=listener.accept();b.settimeout(1);return a,b
a,b=pair(); resets=0;count=0;nonce=uuid.uuid4().hex
while True:
 try:
  a.sendall(b'x');assert b.recv(1)==b'x';b.sendall(b'y');assert a.recv(1)==b'y'
 except (OSError,AssertionError):
  resets+=1;a.close();b.close();a,b=pair()
 count+=1
 with open('/tmp/tcp.next','w') as f:json.dump(dict(pid=os.getpid(),nonce=nonce,resets=resets,count=count),f)
 os.replace('/tmp/tcp.next','/tmp/tcp.json');time.sleep(.01)
'''
owned=[];report={}
def run(s,c):
 r=s.commands.run(c,user='root',timeout=20);assert r.exit_code==0,(c,r.stderr);return r.stdout.strip()
def state(s):return json.loads(run(s,'cat /tmp/tcp.json'))
try:
 p=Sandbox.create('base',timeout=180);owned.append(p)
 run(p,'printf %s '+shlex.quote(code)+' > /tmp/tcp.py; nohup python3 /tmp/tcp.py >/tmp/tcp.log 2>&1 </dev/null &')
 for _ in range(100):
  if run(p,'test -f /tmp/tcp.json && echo yes || true')=='yes':break
  time.sleep(.01)
 before=state(p)
 req=urllib.request.Request(url+'/sandboxes/'+p.sandbox_id+'/fork',data=b'{"timeout":180}',headers={'X-API-Key':key,'Content-Type':'application/json'})
 desc=json.load(urllib.request.urlopen(req,timeout=120))[0]['sandbox'];c=Sandbox.connect(desc['sandboxID']);owned.append(c)
 for _ in range(100):
  a,b=state(p),state(c)
  if b['resets']>=1:break
  time.sleep(.01)
 assert a['resets']==0 and b['resets']==1,(a,b)
 assert a['nonce']==b['nonce']==before['nonce'] and a['pid']==b['pid']
 time.sleep(.05);after=state(c);assert after['count']>b['count'] and after['resets']==1
 c.kill();owned.remove(c);a2=state(p);assert a2['count']>a['count'] and a2['resets']==0
 report=dict(success=True,parent=a2,child=after,parent_connection_preserved=True,child_inherited_connection_reset=True,child_listener_and_new_connections_work=True,parent_survives_child_destroy=True)
finally:
 for s in owned:s.kill()
 (M/'results/five-rounds-108/round5/tcp-validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
