import sys,json,time,urllib.request,os,struct
from pathlib import Path
sys.path.insert(0,'/home/hong/deploy/comparison/sixway')
import runner as b
b.pr='kuasar-fork';b.setup(b.pr)
from e2b import Sandbox
P=Path('/home/hong/deploy/kuasar-fork-research');D=Path('/home/hong/data/kuasar-fork');R=Path('/home/hong/results/sixway-pilot')
def ready(s):
 for _ in range(400):
  info=s.get_info();m=info.metadata
  if m.get('kuasar.network.status')=='ready':return m['kuasar.network.ip']
  if m.get('kuasar.network.status')=='failed':raise RuntimeError('CNI failed')
  time.sleep(.05)
 raise TimeoutError('network')
def childof(s):
 req=urllib.request.Request(b.c['api_url']+'/sandboxes/'+s.sandbox_id+'/fork',data=b'{"count":1,"timeout":300}',headers={'X-API-Key':b.c['api_key'],'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=60) as f:r=json.load(f)
 return Sandbox.connect(r[0]['sandbox']['sandboxID'],timeout=300)
def pages(pid):
 for line in Path(f'/proc/{pid}/maps').read_text().splitlines():
  a=line.split();lo,hi=map(lambda x:int(x,16),a[0].split('-'))
  if hi-lo==2048*1024**2 and a[1]=='rw-p' and a[4]=='0':break
 else:raise AssertionError('private RAM absent')
 with open(f'/proc/{pid}/pagemap','rb') as f:
  f.seek(lo//4096*8);data=f.read((hi-lo)//4096*8)
 return [x&((1<<55)-1) if x>>63 else None for (x,) in struct.iter_unpack('Q',data)]
parent=child=None
try:
 parent=b.create();pip=ready(parent);b.cmd(parent,'/bin/fork-probe >/dev/null 2>&1 &')
 for _ in range(100):
  if b.cmd(parent,'cat /run/probe-ready 2>/dev/null || true')=='10':break
  time.sleep(.05)
 else:raise AssertionError('probe')
 child=childof(parent);cip=ready(child);assert pip!=cip
 records=json.loads((D/'adapter-state.json').read_text());pa=pages(records[parent.sandbox_id]['pid']);ca=pages(records[child.sandbox_id]['pid'])
 fd=os.open('/proc/kpageflags',os.O_RDONLY);shared=0
 for p,c in zip(pa,ca):
  if p is not None and p==c and not (struct.unpack('Q',os.pread(fd,8,p*8))[0]&(1<<24)):shared+=1
 os.close(fd);assert shared>8192,shared
 b.cmd(parent,'echo 20 > /run/probe-command');b.cmd(child,'echo 30 > /run/probe-command')
 for _ in range(100):
  po=b.cmd(parent,'cat /run/probe-result 2>/dev/null || true');co=b.cmd(child,'cat /run/probe-result 2>/dev/null || true')
  if po=='initial=10 value=20' and co=='initial=10 value=30':break
  time.sleep(.05)
 else:raise AssertionError((po,co))
 b.cmd(parent,'/bin/busybox ping -c 1 -W 2 '+cip);b.cmd(child,'/bin/busybox ping -c 1 -W 2 '+pip)
 b.kill(parent);parent=None;assert b.cmd(child,'cat /run/probe-result')==co;b.kill(child);child=None
 parent=b.create();ready(parent);child=childof(parent);ready(child);b.kill(child);child=None;assert b.cmd(parent,'printf SURVIVED')=='SURVIVED';b.kill(parent);parent=None
 assert not list(D.rglob('memory.img'));assert json.loads((D/'adapter-state.json').read_text())=={}
 proof=dict(shared_nonzero_pages=shared,guest_ram_mib=2048,probe_mib=32,parent=po,child=co,separate_ip=True,bidirectional_ping=True,both_destroy_orders=True,memory_img_count=0)
 (R/'fork-validation.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
finally:
 for s in [child,parent]:
  if s:b.kill(s)
