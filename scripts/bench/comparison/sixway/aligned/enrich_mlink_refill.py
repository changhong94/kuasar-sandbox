from pathlib import Path
import json,datetime,statistics,collections
B=Path('/home/hong/src/research/sixway-aligned-20261117');raw=json.loads((B/'results/mlink-events.json').read_text());events=[]
for d in raw:
 us=int(datetime.datetime.fromisoformat(d['timestamp'].replace('Z','+00:00')).timestamp()*1e6)
 events.append((us,d['fields']))
groups=collections.defaultdict(list)
for p in (B/'results/startup').glob('[0-9][0-9]-kuasar-mlink.json'):
 d=json.loads(p.read_text());lo=d['start_unix_ns']//1000;hi=lo+int(d['lifecycle_through_refill_ms']*1000)
 matched=[e for t,e in events if lo<=t<=hi and e.get('event') in ['pico_slot_prepare','runtime_slot_prepare_execution','image_pool_build_execution','pico_cleanup']]
 d['background_events']=matched;d['background_attribution']='Dedicated serial instance, no other requests in the case interval; window uses same-host wall clock correlation. Durations are original server timers.';p.write_text(json.dumps(d,indent=2))
 if p.name.startswith('00-'):continue
 for e in matched:
  if 'total_us' in e:groups[e['event']].append(e['total_us']/1000)
result={k:dict(events=len(v),median_ms=statistics.median(v),max_ms=max(v)) for k,v in groups.items()}
(B/'results/mlink-background-summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
