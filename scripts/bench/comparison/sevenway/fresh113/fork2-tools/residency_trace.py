import pathlib,json,time,sys,subprocess
from e2b import Sandbox
from cache_state import residency
R=pathlib.Path('/home/hong/src/research/sevenway-current-20261126/fork2');D=R/'results/snapshot-start4-opt'
a=json.load(open('/srv/fork2/console.json'));t=json.load(open(R/'results/snapshot-local/python/template.json'));opts=dict(api_key=a['key'],api_url=a['api'],sandbox_url='http://127.0.0.1:19211')
rows=[]
def sample(stage):
 data=[]
 for p in pathlib.Path('/srv/fork2/data/template-memory-cache-v2').glob('*.ram'):
  r=residency(p);r['inode']=p.stat().st_ino;data.append(r)
 rows.append({'stage':stage,'ns':time.time_ns(),'files':data});print(stage,[(p['inode'],p['resident_data_pages'])for p in data],flush=True)
sample('before');s=Sandbox.create(t['templateID'],timeout=300,metadata=t.get('metadata',{}),**opts)
try:
 r=s.commands.run('/usr/local/bin/python3 -c "print(314159)"',user='root',cwd='/',timeout=60);assert r.exit_code==0
 for i in range(8):sample('live-'+str(i));time.sleep(1)
finally:s.kill()
for i in range(8):sample('deleted-'+str(i));time.sleep(1)
(D/'residency-trace.json').write_text(json.dumps(rows,indent=2))
