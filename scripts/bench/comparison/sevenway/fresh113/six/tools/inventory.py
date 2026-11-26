from pathlib import Path
import json,sys,subprocess as sp
import runner as b
p=sys.argv[1];b.pr=p;b.setup(p)
if p=='kuasar-fork':
 root=Path('/home/hong/src/research/python-latest-113')
 sys.path.insert(0,str(root/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'))
 import vm_rpc
 records=json.loads((root/'data/fork/adapter-state.json').read_text())
 assert len(records)==64 and all(d.get('pool_state')=='ready' for d in records.values())
 native=vm_rpc.admin(root/'deploy/fork/admin.sock','sandbox-list')['sandboxes']
 assert {d['id'] for d in native}==set(records)|{'py113seed001'}
 data=dict(product=p,sandbox_ids=[],method='native sandbox-list + durable adapter metadata; SDK list unsupported (501)',native_count=len(native),prepared_slots=64,seed=1)
elif p=='kuasar-mlink':
 raw=json.loads(sp.check_output(b.ctl+['list','--json'],text=True));data=dict(product=p,result=raw)
else:
 from e2b import Sandbox
 pager=Sandbox.list();ids=[]
 while pager.has_next:ids.extend(s.sandbox_id for s in pager.next_items())
 data=dict(product=p,sandbox_ids=ids)
out=Path('/home/hong/src/research/sevenway-current-20261126/six/results')/('inventory-'+p+'.json');out.write_text(json.dumps(data,indent=2));print(json.dumps(data))
