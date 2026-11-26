"""Measured preparation work vs policy wait; no division of concurrent time by slots."""
import datetime,json,math,statistics
from pathlib import Path
B=Path('/home/hong/src/research/sevenway-current-20261126/six')
def stats(x):
 x=sorted(x)
 if not x:return None
 return dict(n=len(x),median=statistics.median(x),p95=x[math.ceil(len(x)*.95)-1],p99=x[math.ceil(len(x)*.99)-1],max=x[-1])
rows=[json.loads(x) for x in Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json.pool-events.jsonl').read_text().splitlines()]
first=json.loads((B/'results/matrix/python/kuasar-fork/local_warm/01.json').read_text())['start_ns']
completed=[x for x in rows if x['event']=='startup_complete' and x['monotonic_ns']<=first]
epoch=completed[-1]['epoch'];initial=[x for x in rows if x.get('epoch')==epoch and x['event']=='prepared' and x['reason']=='startup']
assert len(initial)==64
result={'fork':{'preparation':{'capacity':64,'concurrency':8,'single_slot_ms':stats([x['elapsed_ms'] for x in initial]),'all_slots_loop_ms':completed[-1]['elapsed_ms'],'definition':'parallel pool startup entry to 64 ready; excludes common parent and image-template preparation','events':initial}},'mlink':{},'samples':[]}
log=[]
with Path('/home/hong/data/mlink-generic/ttlet.log').open() as f:
 for line in f:
  try:d=json.loads(line)
  except ValueError:continue
  if d.get('fields',{}).get('event') in ('pico_slot_prepare','runtime_slot_prepare_execution','image_pool_build_execution','pico_cleanup'):log.append(d)
current_run=next(d['fields']['run_id'] for d in reversed(log) if d['fields'].get('run_id'))
initial_m=[d for d in log if d['fields'].get('run_id')==current_run and d['fields'].get('event')=='runtime_slot_prepare_execution' and d['fields'].get('success')][:64]
assert len(initial_m)==64
mfields=[d['fields'] for d in initial_m]
result['mlink']['preparation']={'capacity':64,'concurrency':8,'single_slot_ms':stats([d['total_us']/1000 for d in mfields]),'first_slot_start_to_64_ready_ms':(max(d['finished_mono_us'] for d in mfields)-min(d['started_mono_us'] for d in mfields))/1000,'definition':'first recorded slot preparation start to completion of the first 64 successful slots in this isolated service run; excludes common image/storage preparation','events':initial_m}
initial_start=min(d['monotonic_ns']-int(d['elapsed_ms']*1e6) for d in initial)
result['fork']['preparation']['first_slot_start_to_64_ready_ms']=(max(d['monotonic_ns'] for d in initial)-initial_start)/1e6
for product in ('kuasar-fork','kuasar-mlink'):
 for language in ('python',):
  mode='local_warm' if product=='kuasar-fork' else 'product_default_warm'
  samples=[json.loads((B/f'results/matrix/{language}/{product}/{mode}/{i:02d}.json').read_text()) for i in range(1,51)]
  details=[]
  for s in samples:
   assert s['success'] and s['destroyed']
   if product=='kuasar-fork':
    events=[x for x in rows if x.get('vacancy_sid')==s['sandbox_id'] and x['event']=='prepared']
    work=[x['elapsed_ms'] for x in events]
    retired=[x for x in rows if x['event']=='vacated' and x.get('sid')==s['sandbox_id']]
    starts=[x for x in rows if x['event']=='prepare_started' and x.get('vacancy_sid')==s['sandbox_id']]
    scheduling_ms=(starts[0]['monotonic_ns']-retired[0]['monotonic_ns'])/1e6 if starts and retired else None
   else:
    start=s['start_unix_ns']/1e9;end=start+s['lifecycle_through_refill_ms']/1000
    events=[]
    for e in log:
     if e['fields'].get('event')!='runtime_slot_prepare_execution':continue
     t=datetime.datetime.fromisoformat(e['timestamp'].replace('Z','+00:00')).timestamp()
     if start<=t<=end:events.append(e)
    work=[x['fields']['total_us']/1000 for x in events]
    scheduling_ms=None
   details.append({'sandbox_id':s['sandbox_id'],'delete_ms':s['delete_ms'],'remaining_full_pool_wait_after_delete_ms':s['pool_after']['elapsed_ms'],'create_through_full_pool_ms':s['lifecycle_through_refill_ms'],'slot_work_ms':work,'claim_to_refill_start_ms':scheduling_ms,'events':events})
  result['samples'].append({'product':product,'language':language,'mode':mode,'n':50,'delete_ms':stats([d['delete_ms'] for d in details]),'remaining_full_pool_wait_after_delete_ms':stats([d['remaining_full_pool_wait_after_delete_ms'] for d in details]),'slot_work_ms':stats([v for d in details for v in d['slot_work_ms']]),'claim_to_refill_start_ms':stats([d['claim_to_refill_start_ms'] for d in details if d['claim_to_refill_start_ms'] is not None]),'details':details})
result['wait_policies']={'fork':'No artificial refill delay; durable lease opens a reserve vacancy and wakes refill immediately. Running instances do not occupy reserve capacity. Preparation failures retain retry backoff.','mlink':'1000 ms foreground quiet period protects requests from background preparation; foreground floor refill and active-request handling are separate.'}
(B/'results/pool-analysis.json').write_text(json.dumps(result,indent=2))
print('pool preparation and per-case refill analysis complete')
