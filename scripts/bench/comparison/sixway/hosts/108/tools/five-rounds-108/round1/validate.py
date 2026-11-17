import os,sys,json,time,shlex,urllib.request,struct
from pathlib import Path
M=Path('/opt/bench108');sys.path.insert(0,str(M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'));import vm_rpc
key=(M/'deploy/fork/api-key').read_text().strip();url='http://127.0.0.1:18887'
os.environ.update(E2B_API_KEY=key,E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
from e2b import Sandbox
code='''import os,time,json,uuid
buf=bytearray([10])*(16*1024*1024)
nonce=str(uuid.uuid4());count=0
while True:
 try:
  value=int(open('/tmp/control').read())
  if value!=buf[0]:buf[:]=bytes([value])*len(buf)
 except FileNotFoundError:pass
 count+=1
 with open('/tmp/state.next','w') as f:json.dump(dict(pid=os.getpid(),nonce=nonce,count=count,value=buf[0],last=buf[-1]),f)
 os.replace('/tmp/state.next','/tmp/state.json');time.sleep(.01)
'''
def run(s,c):
 r=s.commands.run(c,user='root',timeout=30);assert r.exit_code==0,r.stderr;return r.stdout.strip()
def state(s):return json.loads(run(s,'cat /tmp/state.json'))
owned=[];out={}
try:
 p=Sandbox.create('base',timeout=300);owned.append(p)
 run(p,'printf %s '+shlex.quote(code)+' > /tmp/counter.py; nohup python3 /tmp/counter.py >/tmp/counter.log 2>&1 </dev/null &')
 for _ in range(100):
  if run(p,'test -f /tmp/state.json && echo yes || true')=='yes':break
  time.sleep(.01)
 before=state(p)
 req=urllib.request.Request(url+'/sandboxes/'+p.sandbox_id+'/fork',data=b'{"timeout":300}',headers={'X-API-Key':key,'Content-Type':'application/json'})
 desc=json.load(urllib.request.urlopen(req,timeout=180))[0]['sandbox'];c=Sandbox.connect(desc['sandboxID']);owned.append(c)
 a=state(p);b=state(c);assert a['nonce']==b['nonce']==before['nonce'] and a['pid']==b['pid'];assert a['value']==b['value']==10
 info=[vm_rpc.admin(M/'deploy/fork/admin.sock','sandbox-get',sandbox_id=s.sandbox_id)['live_fork'] for s in [p,c]]
 def pages(pid):
  regions=[]
  for line in Path(f'/proc/{pid}/maps').read_text().splitlines():
   cols=line.split();start,end=[int(v,16) for v in cols[0].split('-')]
   if cols[1]=='rw-p' and end-start>=1024**3:regions.append((start,end))
  assert regions
  start,end=max(regions,key=lambda v:v[1]-v[0]);out={}
  with open(f'/proc/{pid}/pagemap','rb',buffering=0) as f:
   for page in range(start//4096,end//4096,64):
    f.seek(page*8);v=struct.unpack('Q',f.read(8))[0]
    if v>>63 and v&((1<<55)-1):out[page]=v&((1<<55)-1)
  return out
 x,y=[pages(i['pid']) for i in info];shared=sum(v==y.get(k) for k,v in x.items());assert shared>0
 run(p,'printf 20 > /tmp/control; printf parent > /tmp/private')
 run(c,'printf 30 > /tmp/control; printf child > /tmp/private')
 for _ in range(100):
  a,b=state(p),state(c)
  if a['value']==a['last']==20 and b['value']==b['last']==30:break
  time.sleep(.01)
 else:raise AssertionError((a,b))
 assert run(p,'cat /tmp/private')=='parent' and run(c,'cat /tmp/private')=='child'
 p.kill();owned.remove(p);assert state(c)['value']==30
 req=urllib.request.Request(url+'/sandboxes/'+c.sandbox_id+'/fork',data=b'{"timeout":120}',headers={'X-API-Key':key,'Content-Type':'application/json'})
 desc=json.load(urllib.request.urlopen(req,timeout=180))[0]['sandbox'];g=Sandbox.connect(desc['sandboxID']);owned.append(g)
 assert state(g)['value']==30
 c.kill();owned.remove(c);assert state(g)['value']==30;g.kill();owned.remove(g)
 out['grandchild_after_parent_destroy']=True
 # Reverse destruction order on independently claimed slots.
 p=Sandbox.create('base',timeout=120);owned.append(p)
 req=urllib.request.Request(url+'/sandboxes/'+p.sandbox_id+'/fork',data=b'{"timeout":120}',headers={'X-API-Key':key,'Content-Type':'application/json'})
 desc=json.load(urllib.request.urlopen(req,timeout=180))[0]['sandbox'];c=Sandbox.connect(desc['sandboxID']);owned.append(c)
 c.kill();owned.remove(c);assert run(p,'printf survivor')=='survivor';p.kill();owned.remove(p)
 out.update(success=True,parent=a,child=b,shared_sampled_pfns=shared,parent_first_survivor=True,child_first_survivor=True)
finally:
 for s in owned:
  try:s.kill()
  except Exception:pass
 (M/'results/five-rounds-108/round1/validation.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
