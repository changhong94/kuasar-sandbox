from pathlib import Path
import json,math,re,statistics as st,sys,collections
B=Path(sys.argv[1])
def stats(v):
 v=sorted(v)
 return dict(n=len(v),median=st.median(v),p95=v[math.ceil(.95*len(v))-1],p99=v[math.ceil(.99*len(v))-1],max=v[-1]) if v else None
r=json.loads((B/'results/burst256/kuasar-fork/result.json').read_text())
e=[json.loads(l) for l in (B/'results/burst256/kuasar-fork/pool-events.jsonl').read_text().splitlines()]
p=sorted([x for x in e if x['event']=='prepared' and x.get('reason')=='refill'],key=lambda x:x['monotonic_ns'])
s=[x for x in e if x['event']=='prepare_started' and x.get('reason')=='refill'];vac={x['sid']:x['monotonic_ns'] for x in e if x['event']=='vacated'}
assert r['batch_valid'] and r['print']['completed']==256 and len(p)==len(s)==len(vac)==256
assert len({x['sid'] for x in p})==len({x['vacancy_sid'] for x in p})==256
assert all(x['monotonic_ns']<r['cleanup_started_ns'] for x in p)
prepared={x['sid'] for x in p};claimed={x['sandbox_id'] for x in r['requests']}
d=collections.defaultdict(list);native=collections.defaultdict(list)
log=B/'host-all.log'
for line in log.read_text().splitlines() if log.exists() else []:
 if 'E2B_TIMING ' in line:
  try:x=json.loads(line.split('E2B_TIMING ',1)[1])
  except ValueError:continue
  stage=x['stage']+(':'+x['action'] if 'action' in x else '')
  if x.get('sid') in prepared and (x['stage'] in ('create_total','create_record','namespace','completion_lock_wait','running_record') or x.get('action') in ('sandbox-pool-prepare','sandbox-snapshot-stage')):
   d['prepare/'+stage].append(x['elapsed_ms'])
  if x.get('sid') in claimed and (x['stage'] in ('pool_lease','pool_assignment_save','snapshot_bind','oci_entrypoint_start')):
   d['claim/'+stage].append(x['elapsed_ms'])
  if x['stage']=='durable_save' and r['start_ns']<=x['started_ns']<max(z['monotonic_ns'] for z in p):
   for k in ('serialize_ms','barrier_ms','projection_ms','elapsed_ms'):
    if k in x:d['persistence/'+k].append(x[k])
 if 'POOL_PREPARE_PHASE' in line:
  line=re.sub(r'\x1b\[[0-9;]*m','',line)
  m=re.search(r'sandbox_id=String\("([^"]+)"\).*phase="([^"]+)".*elapsed_us=(\d+)',line)
  if m and m[1] in prepared:native[m[2]].append(int(m[3])/1000)
summary=dict(all_ready_ms=r['ready']['all_256_ms'],all_print_ms=r['print']['all_256_ms'],completion_gap_ms=stats(r['print']['adjacent_completion_gap_ms']),refill_work_ms=stats([x['elapsed_ms'] for x in p]),claim_to_refill_start_ms=stats([(x['monotonic_ns']-vac[x['vacancy_sid']])/1e6 for x in s]),claim_to_replacement_ready_ms=stats([x['replacement_ms'] for x in p]),full_reserve_after_request_release_ms=(p[-1]['monotonic_ns']-r['start_ns'])/1e6,full_reserve_after_last_print_ms=(p[-1]['monotonic_ns']-max(x['print_ns'] for x in r['requests']))/1e6,held_pool=r['pool_while_instances_retained'],client_dispatch_spread_ms=r['client_dispatch_spread_ms'],image_digest=r['image_digest'],peak_product_pss_mib=r['peak_retained_resources']['pss_mib'],phases={k:stats([x['phases'][k] for x in p]) for k in p[0].get('phases',{})},host_phases={k:stats(v) for k,v in d.items()},native_phases={k:stats(v) for k,v in native.items()},preparation=json.loads((B/'preparation.json').read_text()),deployment=json.loads((B/'deployment.json').read_text()))
(B/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:summary[k] for k in ('all_ready_ms','all_print_ms','completion_gap_ms','refill_work_ms','full_reserve_after_request_release_ms')},indent=2))
