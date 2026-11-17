import json,statistics,pathlib
R=pathlib.Path('/opt/bench108/results/snapshot-pool-108');r=R/'final'; ids={json.loads(p.read_text())['sandbox_id'] for p in r.glob('*-kuasar-fork.json')};v={};ph={};ds=[]
for l in (R/'final-journal.log').read_text().splitlines():
 if not l.startswith('E2B_TIMING '):continue
 d=json.loads(l[11:]);ds.append(d)
 if d.get('sid') in ids:
  v.setdefault(d['stage'],[]).append(d['elapsed_ms'])
  if d['stage']=='snapshot_bind':
   for x in d['details']['phases']:ph.setdefault(x['phase'],[]).append(x['ms'])
e=[json.loads(l) for l in (R/'adapter-state.json.pool-events.jsonl').read_text().splitlines()];ref=[d for d in e if d.get('retired_sid') in ids]
out={'phases_ms':{k:statistics.median(a) for k,a in ph.items()},'adapter_ms':{k:statistics.median(a) for k,a in v.items()},'first_command_client_ms':statistics.median(json.loads(p.read_text())['ready_ms']-json.loads(p.read_text())['api_ms'] for p in r.glob('*-kuasar-fork.json')),'refill':{k:statistics.median(d[k] for d in ref) for k in ('elapsed_ms','replacement_ms')},'refill_n':len(ref),'pool_startup':next(x for x in e if x['event']=='startup_complete')}
(R/'final-phases.json').write_text(json.dumps(out,indent=2))
c=[d for d in ds if d.get('action')=='sandbox-snapshot-capture'][-1]; sid=c['sid'];first=next(d for d in ds if d.get('sid')==sid and d['stage']=='create_record');end=next(d for d in ds if d.get('sid')==sid and d.get('action')=='sandbox-destroy')['ended_ns'];clean=next(d for d in ds if d['stage']=='durable_save' and d['started_ns']>end)
start=int((R/'final-service-start-us.txt').read_text()); rows=[json.loads(l) for l in (R/'final-deployment-journal.jsonl').read_text().splitlines()];listen=[d for d in rows if 'E2B compatible API listening' in str(d.get('MESSAGE',''))][-1]
p={'total_builder_prepare_warm_cleanup_ms':(clean['ended_ns']-first['started_ns'])/1e6,'post_destroy_cni_state_ms':(clean['ended_ns']-end)/1e6,'service_start_to_api_listen_ms':(int(listen['__MONOTONIC_TIMESTAMP'])-start)/1000};(R/'final-preparation-total.json').write_text(json.dumps(p,indent=2));print(json.dumps({'phases':out,'preparation':p},indent=2))
