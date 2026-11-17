"""Join server phases by sandbox ID; retain raw evidence and unavailable values."""
from pathlib import Path
import json,subprocess as sp,datetime
B=Path('/home/hong/src/research/sixway-aligned-20261117');R=B/'results/startup'
rows=[(p,json.loads(p.read_text())) for p in R.glob('[0-9][0-9]-*.json')]
first=min(d['start_unix_ns'] for p,d in rows)/1e9
raw=sp.check_output(['journalctl','-u','bench-python113-fork','--since','@'+str(int(first)-1),'-o','cat','--no-pager'],text=True)
(B/'results/fork-events.log').write_text(raw)
pool_path=Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json.pool-events.jsonl')
pool_events=[json.loads(v) for v in pool_path.read_text().splitlines()]
(B/'results/fork-pool-events.json').write_text(json.dumps(pool_events,indent=2))
fork=[]
for line in raw.splitlines():
 if 'E2B_TIMING ' in line:
  try:fork.append(json.loads(line.split('E2B_TIMING ',1)[1]))
  except ValueError:pass
mlink=[]
for line in Path('/home/hong/data/mlink-generic/ttlet.log').read_text().splitlines():
 try:
  d=json.loads(line)
  if datetime.datetime.fromisoformat(d['timestamp'].replace('Z','+00:00')).timestamp()>=first:mlink.append(d)
 except (ValueError,KeyError):pass
(B/'results/mlink-events.json').write_text(json.dumps(mlink,indent=2))
for p,d in rows:
 sid=d['sandbox_id'];events=[]
 if d['product']=='kuasar-fork':events=[e for e in fork if e.get('sid')==sid and e['started_ns']>=d['start_ns']]
 elif d['product']=='kuasar-mlink':events=[e['fields'] for e in mlink if (e.get('fields',{}).get('thinkactor_name') in (sid,'thinkactor-'+sid) or e.get('fields',{}).get('thinkactor_id')==sid)]
 d['refill_events']=[e for e in pool_events if e.get('retired_sid')==sid] if d['product']=='kuasar-fork' else []
 d['internal_phases']=events;d['internal_ready_ms']=None
 for e in events:
  if e.get('event')=='pico_restore':d['internal_ready_ms']=(e['guest_ready_finished_unix_us']*1000-d['start_unix_ns'])/1e6;d['internal_ready_clock']='server/client CLOCK_REALTIME, same host; primary elapsed timings remain monotonic'
 d['internal_phase_note']='Matched by sandbox ID; overlapping phases must not be added. Missing phases are unobservable, not zero.'
 p.write_text(json.dumps(d,indent=2))
