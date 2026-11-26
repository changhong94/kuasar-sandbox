from pathlib import Path
import json
B=Path('/home/hong/src/research/sixway-aligned-20261117');rows=[]
for p in (B/'results/startup').glob('[0-9][0-9]-*.json'):
 d=json.loads(p.read_text())
 if d['product'] not in ['kuasar-fork','kuasar-mlink']:continue
 for k in ['pool_before','pool_after']:
  v=d[k]['state']
  if d['product']=='kuasar-fork':
   assert v['capacity']==v['ready']==v['owned']==2 and v['assigned']==0 and not v['preparing'] and not v['last_error'] and v['misses']==0,(p,k,v)
  else:
   assert v['capacity']['configured']==v['capacity']['ready']==2
   for key in ['assigned','preparing','recycling','rearming','retiring','failed']:assert v['capacity'][key]==0,(p,k,key,v['capacity'])
   assert v['thinkactors']==v['operations']==0
   tpl=next(t for t in v['templates'] if t['id']==json.loads((B/'tools/config.json').read_text())['kuasar-mlink']['template'])
   assert tpl['storage_ready']==2 and tpl['storage_users']==tpl['storage_preparing']==tpl['storage_warming']==tpl['memory_users']==0 and tpl['memory_cache']['full']
  rows.append(dict(file=p.name,position=k,ok=True))
(B/'results/readiness-audit.json').write_text(json.dumps(dict(gates=len(rows),all_ready=True,checks=rows),indent=2));print('Passed',len(rows),'pool states')
