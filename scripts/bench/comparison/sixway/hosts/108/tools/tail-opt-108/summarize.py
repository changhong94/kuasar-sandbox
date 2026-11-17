import json,pathlib,statistics
R=pathlib.Path('/opt/bench108/results/tail-opt-108')
for run in ('baseline','final','v2','v3','v4'):
 r=R/run
 if not (r/'summary.json').exists():continue
 ids={json.loads(p.read_text())['sandbox_id'] for p in r.glob('*-kuasar-fork.json')}
 ds=[json.loads(l[11:]) for l in (R/(run+'.log')).read_text().splitlines() if l.startswith('E2B_TIMING ')]
 selected=[d for d in ds if d.get('sid') in ids];ph={};st={};commits=[]
 for d in selected:
  st.setdefault(d['stage'],[]).append(d['elapsed_ms'])
  if d['stage']=='snapshot_bind':
   for x in d['details']['phases']:ph.setdefault(x['phase'],[]).append(x['ms'])
  if d['stage']=='pool_assignment_save':
   commits += [x for x in ds if x['stage']=='durable_save' and d['started_ns'] <= x['started_ns'] and x['ended_ns'] <= d['ended_ns']]
 def stats(a):return {'n':len(a),'median':statistics.median(a),'max':max(a)}
 out={'phases':{k:stats(a) for k,a in ph.items()},'stages':{k:stats(a) for k,a in st.items()},'lease_commit':{k:stats([d[k] for d in commits]) for k in ('serialize_ms','begin_ms','update_ms','barrier_ms','projection_ms','commit_ms')},'lease_changed_records':[d.get('changed_records') for d in commits],'lease_changed_bytes':[d.get('changed_bytes') for d in commits]}
 (R/(run+'-phases.json')).write_text(json.dumps(out,indent=2));print(run,json.dumps(out))
