from pathlib import Path
import json,math,statistics,collections,sys
B=Path(sys.argv[1]);summary={}
def stats(v):
 v=sorted(v);return dict(n=len(v),median=statistics.median(v),p95=v[math.ceil(.95*len(v))-1],p99=v[math.ceil(.99*len(v))-1],max=v[-1]) if v else None
for name in ('8','16','32','64','8-repeat'):
 b=B/name;p=b/'results/burst256/kuasar-fork/result.json'
 if not p.exists():continue
 r=json.loads(p.read_text());assert r['batch_valid'] and not r['public_remaining']
 assert r['all_returned_instances_retained'] and r['all_private_files_verified'] and r['survivors_verified_after_half_destroyed']
 e=[json.loads(l) for l in (p.parent/'pool-events.jsonl').read_text().splitlines()];v={x['sid']:x['monotonic_ns'] for x in e if x['event']=='vacated'};starts=[x for x in e if x['event']=='prepare_started' and x['reason']=='refill'];done=[x for x in e if x['event']=='prepared' and x['reason']=='refill']
 assert len(v)==len(done)==len(starts)==256
 summary[name]=dict(successes=r['print']['completed'],failed=r['failed_requests'],all_print_s=r['print']['all_256_ms']/1000 if r['print']['all_256_ms'] else None,last_success_s=r['print']['last_success_ms']/1000,all_requests_settled_s=r['all_requests_settled_ms']/1000,refill_work_ms=stats([x['elapsed_ms'] for x in done]),completion_gap_ms=stats(r['print']['adjacent_completion_gap_ms']),queue_ms=stats([(x['monotonic_ns']-v[x['vacancy_sid']])/1e6 for x in starts]),last_refill_s=(max(x['monotonic_ns'] for x in done)-r['start_ns'])/1e9,peak_inflight=max(x.get('inflight',0) for x in starts),errors=dict(collections.Counter(x.get('error','') for x in r['requests'] if not x['success'])),held_pool=r['pool_while_instances_retained'],final_pool=r['pool_after'],pss_mib=r['peak_retained_resources']['pss_mib'],image_digest=r['image_digest'],dispatch_spread_ms=r['client_dispatch_spread_ms'],service_prepare_s=json.loads((b/'deployment.json').read_text())['service_to_ready_ms']/1000,image_prepare_s=json.loads((b/'preparation.json').read_text())['template_prepare_publish_first_create_ms']/1000)
(B/'comparison.json').write_text(json.dumps(summary,indent=2));print(json.dumps({k:{f:v[f] for f in ('successes','all_print_s','last_success_s','all_requests_settled_s','peak_inflight','errors')} for k,v in summary.items()},indent=2))
