from pathlib import Path
import json,statistics,collections
B=Path('/home/hong/src/research/sixway-aligned-20261117');out={}
for n in ['kuasar-mlink','kuasar-fork']:
 groups=collections.defaultdict(list);counts=collections.Counter()
 for p in (B/'results/startup').glob('[0-9][0-9]-'+n+'.json'):
  if p.name.startswith('00-'):continue
  d=json.loads(p.read_text())
  for e in d['internal_phases']:
   event=e.get('stage') or e.get('event');counts[event]+=1
   if e.get('started_ns',d['start_ns'])>d['received_ns']:continue
   if 'elapsed_ms' in e:groups[event+'.elapsed_ms'].append(e['elapsed_ms'])
   for k,v in e.items():
    if k.endswith('_us') and isinstance(v,(int,float)) and not any(x in k for x in ['mono','unix','started','finished','returned']):groups[event+'.'+k[:-3]+'_ms'].append(v/1000)
  for e in d.get('refill_events',[]):
   for k in ['elapsed_ms','replacement_ms']:
    if k in e:groups['refill.'+k].append(e[k])
 out[n]=dict(event_counts=counts,phases={k:dict(n=len(v),median=statistics.median(v),max=max(v)) for k,v in groups.items()})
(B/'results/internal-phases-summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
