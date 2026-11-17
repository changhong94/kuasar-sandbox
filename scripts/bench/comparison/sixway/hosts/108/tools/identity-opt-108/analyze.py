from pathlib import Path
import json,re,statistics,collections,hashlib,shutil
M=Path('/opt/bench108');R=M/'results/identity-opt-108';B=M/'results/language-matched-108';T=M/'tools/identity-opt-108'
raw=re.sub(r'\x1b\[[0-9;]*m','',(R/'fork-timing.log').read_text());events=[];pipeline={};guest={}
for l in raw.splitlines():
 if 'E2B_TIMING ' in l:events.append(json.loads(l.split('E2B_TIMING ',1)[1]))
 if 'snapshot resume/connect/identity pipeline' in l:
  sid=re.search(r'sandbox_id=(\S+)',l).group(1);pipeline[sid]={k:int(re.search(k+r'=(\d+)',l).group(1))/1000 for k in ['resume_us','connect_us','identity_us']}
 if 'FORK_GUEST_PHASE ' in l:
  sid,data=l.split('FORK_GUEST_PHASE ',1)[1].split(' ',1);guest[sid]=dict(json.loads(data))
ml=[json.loads(l)['fields'] for l in (M/'data/mlink-lang/ttlet.log').read_text().splitlines()]
summary={};allrows=[];refills=[]
for lang in ['node','ruby']:
 summary[lang]={};cfg=json.loads((T/(lang+'.json')).read_text())
 for product in ['kuasar-fork','kuasar-mlink']:
  a=[json.loads(p.read_text()) for p in (R/lang).glob('[0-9][0-9]-'+product+'.json')];assert len(a)==10;allrows+=a;ids={x['sandbox_id'] for x in a}
  for x in a:
   assert x['success'] and x['destroyed'] and x['attempts']==1 and x['received_marker']==x['marker']
   assert x['guest_argv']==['/bin/bash','-l','-c',x['command']] and x['image_digest']==cfg['_image_digest']
   assert x['language_env']==cfg['_env'] and x['ready_ms']==(x['received_ns']-x['start_ns'])/1e6
  d={k:statistics.median(x[k] for x in a) for k in ['ready_ms','api_ms','exec_to_print_ms']};d['max_ms']=max(x['ready_ms'] for x in a)
  if product=='kuasar-fork':
   ev=[x for x in events if x.get('sid') in ids];(R/(lang+'-fork-events.json')).write_text(json.dumps(ev,indent=2))
   binds=[x for x in ev if x['stage']=='snapshot_bind'];assert len(binds)==10
   phases=collections.defaultdict(list)
   for x in binds:
    for p in x['details']['phases']:phases[p['phase']].append(p['ms'])
   d['bind_phases_ms']={k:statistics.median(v) for k,v in phases.items()};d['bind_ms']=statistics.median(x['elapsed_ms'] for x in binds)
   d['pipeline_ms']={k:statistics.median(pipeline[sid][k] for sid in ids) for k in ['resume_us','connect_us','identity_us']}
   d['guest_phase_ms']={k:statistics.median(guest[sid][k]/1000 for sid in ids) for k in next(guest[sid] for sid in ids)}
   d['guest_identity_total_ms']=statistics.median(sum(v for k,v in guest[sid].items() if k not in ['worker_queue','entropy_work','tcp_reset_work'])/1000 for sid in ids)
  else:
   ev=[x for x in ml if x.get('thinkactor_id') in ids or x.get('thinkactor_name','').removeprefix('thinkactor-') in ids];(R/(lang+'-mlink-events.json')).write_text(json.dumps(ev,indent=2))
   restores=[x for x in ev if x.get('event')=='pico_restore'];assert len(restores)==10
   d['restore_ms']={k:statistics.median(x[k]/1000 for x in restores) for k in ['vmm_restore_us','guest_ready_us','total_us']}
  summary[lang][product]=d
assert len({x['marker'] for x in allrows})==40
ids={x['sandbox_id'] for x in allrows if x['product']=='kuasar-fork'}
for l in (M/'data/fork/adapter-state.json.pool-events.jsonl').read_text().splitlines():
 e=json.loads(l)
 if e.get('retired_sid') in ids:refills.append(e)
(R/'refill-events.json').write_text(json.dumps(refills,indent=2))
(R/'stages.json').write_text(json.dumps(summary,indent=2))
assert hashlib.sha256((T/'bench.py').read_bytes()).digest()==hashlib.sha256((M/'tools/language-matched-108/bench.py').read_bytes()).digest()
(R/'verification.json').write_text(json.dumps({'formal_samples':40,'all_first_attempt':True,'all_destroyed':True,'benchmark_script_unchanged':True,'matched_env_command_digest':True,'refill_count':len(refills)},indent=2))
shutil.copyfile(B/'stages.json',R/'baseline-stages.json')
print(json.dumps(summary,indent=2))
