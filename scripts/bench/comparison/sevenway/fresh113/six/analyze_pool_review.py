from pathlib import Path
import json,statistics,math,datetime,collections
B=Path('/home/hong/src/research/sevenway-current-20261126/six');R=B/'results'
def rows(path):
 for line in path.open():
  try:yield json.loads(line)
  except ValueError:pass
def stats(a):
 a=sorted(a)
 return dict(n=len(a),median=statistics.median(a),p95=a[math.ceil(.95*len(a))-1],p99=a[math.ceil(.99*len(a))-1],max=a[-1]) if a else None
fe=list(rows(Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json.pool-events.jsonl')))
initial=[e for e in rows(B/'preparation/fork-startup-events.jsonl') if e['event']=='prepared' and e['reason']=='startup'];assert len(initial)==64
mlink=list(rows(Path('/home/hong/data/mlink-generic/ttlet.log')))
me=[e for e in mlink if e.get('fields',{}).get('event')=='runtime_slot_prepare_execution' and e['fields'].get('success')]
runid=me[-1]['fields']['run_id'];mi=[e['fields'] for e in me if e['fields']['run_id']==runid][:64];assert len(mi)==64
out={'fork':{'preparation':{'concurrency':8,'single_slot_ms':stats([e['elapsed_ms'] for e in initial]),'first_slot_start_to_64_ready_ms':(max(e['monotonic_ns'] for e in initial)-min(e['monotonic_ns']-e['elapsed_ms']*1e6 for e in initial))/1e6}},'mlink':{'preparation':{'concurrency':8,'run_id':runid,'single_slot_ms':stats([e['total_us']/1000 for e in mi]),'first_slot_start_to_64_ready_ms':(max(e['finished_mono_us'] for e in mi)-min(e['started_mono_us'] for e in mi))/1000}},'samples':[]}
for p,mode in [('kuasar-fork','local_warm'),('kuasar-mlink','product_default_warm')]:
 cases=[json.loads((R/f'matrix/python/{p}/{mode}/{i:02d}.json').read_text()) for i in range(1,51)]
 durations=[];delays=[]
 for r in cases:
  if p=='kuasar-fork':
   ev=[e for e in fe if e.get('event')=='prepared' and e.get('vacancy_sid')==r['sandbox_id']]
   assert len(ev)==1,(r['sandbox_id'],len(ev));durations.append(ev[0]['elapsed_ms'])
   start=next(e for e in fe if e.get('event')=='prepare_started' and e.get('vacancy_sid')==r['sandbox_id'])
   vacate=next(e for e in fe if e.get('event')=='vacated' and e.get('sid')==r['sandbox_id'])
   delays.append((start['monotonic_ns']-vacate['monotonic_ns'])/1e6)
  else:
   left=r['start_unix_ns'];right=left+r['lifecycle_through_refill_ms']*1e6
   assert right>left,r.keys()
   for e in me:
    wall=int(datetime.datetime.fromisoformat(e['timestamp'].replace('Z','+00:00')).timestamp()*1e9)
    if left<=wall<=right:durations.append(e['fields']['total_us']/1000)
 out['samples'].append({'product':p,'language':'python','delete_ms':stats([r['delete_ms'] for r in cases]),'remaining_full_pool_wait_after_delete_ms':stats([r['pool_after']['elapsed_ms'] for r in cases]),'slot_work_ms':stats(durations),'lease_to_refill_start_ms':stats(delays)})
(R/'pool-analysis.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
