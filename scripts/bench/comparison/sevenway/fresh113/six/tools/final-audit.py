import json,sys,subprocess as sp,fcntl
from pathlib import Path
B=Path('/home/hong/src/research/sevenway-current-20261126/six');T=B/'tools';R=B/'results';sys.path.insert(0,str(T))
from languages import PRODUCTS
c=json.loads((T/'config.json').read_text())
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for n in PRODUCTS:
  sp.run(['nsenter','--net=/run/netns/'+c[n]['netns'],sys.executable,str(T/'inventory-after.py'),n],check=True)
rows=[]
for language in ['python','node','ruby']:
 d=R/'matrix'/language
 for n in PRODUCTS:
  samples=[json.loads((d/f'{i:02d}-{n}.json').read_text()) for i in range(1,51)]
  assert all(x['success'] and x['destroyed'] and x['attempts']==1 for x in samples)
  assert len({x['marker'] for x in samples})==50
  lifecycle=json.loads((R/f'independent-{n}-{language}.json').read_text())
  assert all(lifecycle[str(v)]['success'] and lifecycle[str(v)]['isolated_files'] for v in [0,1])
  assert not list(d.glob('*.ledger'))
  rows.append({'language':language,'product':n,'samples':50,'warmup':1,'independent_destroy_orders':2})
(R/'final-audit.json').write_text(json.dumps({'passed':True,'groups':rows,'measured_samples':900,'warmup_samples':18},indent=2));print('FINAL_AUDIT_PASSED')
