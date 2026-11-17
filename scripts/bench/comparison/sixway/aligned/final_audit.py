from pathlib import Path
import json,time,sys,hashlib,subprocess as sp
B=Path('/home/hong/src/research/sixway-aligned-20261117');R=B/'results';T=B/'tools';assert (R/'complete.json').exists();sys.path.insert(0,str(T));import runner as b
rows=[json.loads(p.read_text()) for p in (R/'timing').glob('[1-5]-*.json')];assert len(rows)==30
assert all(d['success'] and not d['owned_remaining'] and not d.get('cleanup_error') for d in rows)
pressure=[x for d in rows for x in d['pressure']];assert len(pressure)==240 and all(x['success'] for x in pressure)
store=[json.loads(p.read_text()) for p in (R/'timing/storage').glob('[1-3]-*.json')];assert len(store)==36 and all(d['success'] and not d['remaining'] for d in store)
cases=[]
for mode in ['growth','default','100','random']:
 for n in b.prods:
  f=R/('growth' if mode=='growth' else 'arrays')/(n+('' if mode=='growth' else '-'+mode)+'.json');d=json.loads(f.read_text());assert not any(d.get(k) for k in ['owned','error','cleanup_error','cleanup_errors'])
  assert d.get('verified')==50 if mode=='growth' else d.get('success')
  cases.append(str(f.relative_to(R)))
for p in (R/'timing').glob('*.ledger'):assert json.loads(p.read_text())==[]
sp.run(['nsenter','--net=/run/netns/py113-fork',sys.executable,'/home/hong/src/research/python-latest-113/tools/wait-ready.py'],check=True,stdout=(R/'fork-final-pool.json').open('w'))
inventories={}
for n in b.prods:
 sp.run(['nsenter','--net=/run/netns/'+b.ns[n],sys.executable,T/'inventory.py',n],check=True)
 d=json.loads((R/('inventory-'+n+'.json')).read_text());inventories[n]=d
 if n!='kuasar-mlink':assert d['sandbox_ids']==[],d
 else:
  raw=d['result'];assert raw==[] or (isinstance(raw,dict) and raw.get('instances')==[]),raw
state=json.loads((R/'fork-final-pool.json').read_text());assert state['ready']==64 and state['assigned']==0
b.pr='kuasar-fork';resources=b.resources();seed=json.loads(Path('/home/hong/src/research/python-latest-113/deploy/fork/seed-preparation.json').read_text());pid=str(seed['pid']);fd=len(list(Path('/proc',pid,'fd').iterdir()));first=[d for d in rows if d['product']=='kuasar-fork' and str(d['round'])=='1'][0]['stages']['before']['processes'][pid][2]
assert fd==first,('seed FD changed',first,fd)
startup=[json.loads(p.read_text()) for p in (R/'startup').glob('[0-9][0-9]-*.json') if not p.name.startswith('00-')]
assert len(startup)==300 and len({d['marker'] for d in startup})==300
assert all(d['success'] and d['destroyed'] and d['attempts']==1 for d in startup)
assert json.loads((R/'readiness-audit.json').read_text())['all_ready']
out=dict(startup_samples=300,startup_warmups=6,ready_pool_states_verified=204,complete=True,timing_cases=30,pressure_requests=240,storage_cases=36,memory_cases=len(cases),all_workloads_verified=True,all_owned_cleaned=True,all_product_inventory_empty=True,fork_pool_ready=64,fork_pool_assigned=0,fork_seed_fd_before=first,fork_seed_fd_after=fd,time=time.time(),tool_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in T.glob('*.py')})
(R/'final-audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
