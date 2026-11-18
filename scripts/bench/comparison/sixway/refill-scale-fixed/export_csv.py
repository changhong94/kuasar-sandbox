from pathlib import Path
import csv,json,sys
b=Path(sys.argv[1]);out=b/'report';out.mkdir(exist_ok=True)
with (out/'completion-intervals.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['workers','completion_rank','print_ms_since_release','gap_from_previous_ms'])
 for k in ('8','16','32','64'):
  r=json.loads((b/k/'results/burst256/kuasar-fork/result.json').read_text());v=r['print']['completion_ms']
  for i,t in enumerate(v):w.writerow([k,i+1,t,t-v[i-1] if i else ''])
with (out/'refill-times.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['workers','refill_completion_rank','work_ms','completed_ms_since_request_release'])
 for k in ('8','16','32','64'):
  r=json.loads((b/k/'results/burst256/kuasar-fork/result.json').read_text());events=[json.loads(l) for l in (b/k/'results/burst256/kuasar-fork/pool-events.jsonl').read_text().splitlines()]
  v=sorted([e for e in events if e['event']=='prepared' and e.get('reason')=='refill'],key=lambda e:e['monotonic_ns'])
  for i,e in enumerate(v):w.writerow([k,i+1,e['elapsed_ms'],(e['monotonic_ns']-r['start_ns'])/1e6])
