import json,statistics,pathlib,sys
R=pathlib.Path('/opt/bench108/results/snapshot-opt-108');run=sys.argv[1];r=R/run
ids={json.loads(p.read_text())['sandbox_id'] for p in r.glob('*-kuasar-fork.json')};ph={};ad={}
for l in (R/(run+'.log')).read_text().splitlines():
 if not l.startswith('E2B_TIMING '):continue
 d=json.loads(l[11:])
 if d.get('sid') not in ids:continue
 ad.setdefault(d['stage'],[]).append(d['elapsed_ms'])
 if d['stage']=='snapshot_bind':
  for x in d['details']['phases']:ph.setdefault(x['phase'],[]).append(x['ms'])
rows=[json.loads(p.read_text()) for p in r.glob('*-kuasar-fork.json')]
e=[json.loads(l) for l in pathlib.Path('/opt/bench108/data/fork/adapter-state.json.pool-events.jsonl').read_text().splitlines()];ref=[d for d in e if d.get('retired_sid') in ids]
out={'phases_ms':{k:statistics.median(a) for k,a in ph.items()},'adapter_ms':{k:statistics.median(a) for k,a in ad.items()},'command_ms':statistics.median(d['ready_ms']-d['api_ms'] for d in rows),'refill_n':len(ref),'refill':{k:statistics.median(d[k] for d in ref) for k in ('elapsed_ms','replacement_ms')} if ref else {},'success':all(d['success'] and d['destroyed'] for d in rows)}
(R/(run+'-phases.json')).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
