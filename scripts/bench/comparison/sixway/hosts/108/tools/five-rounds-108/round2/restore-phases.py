from pathlib import Path
import json,re,statistics,collections
r=Path('/opt/bench108/results/five-rounds-108/round2');s=(r/'fork-timing.log').read_text();out={}
for lang in ['node','ruby']:
 ids={json.loads(p.read_text())['sandbox_id'] for p in (r/lang).glob('[0-9][0-9]-kuasar-fork.json')};groups=collections.defaultdict(list)
 for line in s.splitlines():
  if 'VM_FORK stage ' not in line:continue
  x=dict(re.findall(r'(op|pid|phase|elapsed_ms|cpu_ms|voluntary|involuntary|run_ns|wait_ns)=([^\s]+)',line));sid=next((sid for sid in ids if sid in x.get('op','')),None)
  if sid:groups[sid].append(x)
 assert len(groups)==10
 stages=collections.defaultdict(list);totals=collections.defaultdict(list)
 for sid,events in groups.items():
  first=events[0];last=events[-1];assert last['phase']=='restore_done'
  for a,b in zip(events,events[1:]):stages[b['phase']].append(float(b['elapsed_ms'])-float(a['elapsed_ms']))
  for k,scale in [('elapsed_ms',1),('run_ns',1e-6),('wait_ns',1e-6),('voluntary',1),('involuntary',1)]:totals[k].append((float(last[k])-float(first[k]))*scale)
 out[lang]={'stage_delta_medians_ms':{k:statistics.median(v) for k,v in stages.items()},'totals_median':{k:statistics.median(v) for k,v in totals.items()},'raw':groups}
(r/'restore-phases.json').write_text(json.dumps(out,indent=2))
for l,v in out.items():print(l,v['totals_median'], sorted(v['stage_delta_medians_ms'].items(),key=lambda x:-x[1])[:7])
