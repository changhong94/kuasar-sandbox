import json,pathlib,statistics
R=pathlib.Path('/opt/bench108/results/tail-next-108')
def stats(a):return {'n':len(a),'median_ms':statistics.median(a),'max_ms':max(a)}
for run in ['baseline','optimized']:
 rows=[json.loads(p.read_text()) for p in (R/run).glob('*-kuasar-fork.json')];ids={d['sandbox_id'] for d in rows}
 ds=[json.loads(l[11:]) for l in (R/(run+'.log')).read_text().splitlines() if l.startswith('E2B_TIMING ')];ph={};st={};commits=[];stage=[]
 for d in ds:
  if d.get('sid') not in ids:continue
  st.setdefault(d['stage'],[]).append(d['elapsed_ms'])
  if d['stage']=='snapshot_bind':
   stage.append(sum(x['ms'] for x in d['details']['phases'] if x['phase'].startswith('stage_')))
   for x in d['details']['phases']:ph.setdefault(x['phase'],[]).append(x['ms'])
  if d['stage']=='pool_assignment_save':
   commits.extend(x for x in ds if x['stage']=='durable_save' and d['started_ns']<=x['started_ns'] and x['ended_ns']<=d['ended_ns'])
 out={'phases':{k:stats(a) for k,a in ph.items()},'stages':{k:stats(a) for k,a in st.items()},'restore_file_work':stats(stage),'lease_commit':{k:stats([d[k] for d in commits]) for k in ['serialize_ms','begin_ms','update_ms','barrier_ms','projection_ms','commit_ms']},'partial_lease_saves':sum(bool(d.get('partial')) for d in commits),'first_command':stats([d['ready_ms']-d['api_ms'] for d in rows]),'all_success_destroyed':all(d['success'] and d['destroyed'] for d in rows)}
 if run=='optimized':
  e=[json.loads(l) for l in (R/'optimized-pool-events.jsonl').read_text().splitlines()];ref=[d for d in e if d.get('retired_sid') in ids];out['refill_n']=len(ref);out['refill']={k:stats([d[k] for d in ref]) for k in ['elapsed_ms','replacement_ms']}
  j=[json.loads(l) for l in (R/'optimized-deployment-journal.jsonl').read_text().splitlines()];start=int((R/'optimized-start-us.txt').read_text());listen=[d for d in j if 'E2B compatible API listening' in str(d.get('MESSAGE',''))][-1];out['startup_ms']=(int(listen['__MONOTONIC_TIMESTAMP'])-start)/1000
 (R/(run+'-phases.json')).write_text(json.dumps(out,indent=2));print(run,json.dumps(out))
