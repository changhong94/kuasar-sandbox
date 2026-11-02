"""Mechanical JSON/CSV aggregation; no narrative conclusions or invented values."""
import csv,json,statistics,sys
from pathlib import Path
D=Path(sys.argv[1]);rows=[]
for item in json.loads((D/'results.json').read_text()):
    out=D/item['name'];r=dict(item)
    if item['case']=='certificate':
        files=list(out.glob('trials/*/agent/fixed-replay.json'));trials=list(out.glob('trials/*/result.json'))
        if files:
            x=json.loads(files[0].read_text());r.update(command_ms=x['elapsed_ms'],command_count=len(x['commands']),model_calls=x['model_calls'],workload_sha256=x['workload_sha256'])
        if trials:r['reward']=(json.loads(trials[0].read_text()).get('verifier_result') or {}).get('rewards',{}).get('reward')
    elif (out/'result.json').exists():
        x=json.loads((out/'result.json').read_text());req=x['requests'];ok=[v for v in req if v.get('success')]
        r.update(successes=len(ok),attempts=len(req),failed=len(req)-len(ok),owned_remaining=len(x['owned_remaining']))
        if ok:r['ready_median_ms']=statistics.median(v['ready_ms'] for v in ok)
        if x.get('load_seconds'):r['completed_tasks_per_second']=sum('workload' in v and v.get('success') for v in req)/x['load_seconds']
        r['baseline_vm_count']=len(x['baseline_vm_pids'])
        r['pss_before_mib']=x['stages']['before']['totals']['all']['Pss']/1024
        r['pss_after_settle_mib']=x['stages']['after_settle']['totals']['all']['Pss']/1024
        r['pss_observed_max_mib']=max(v['totals']['all']['Pss']/1024 for v in x['stages'].values())
        r['pss_scope']='Product selected processes including pre-existing VMs; diagnostic only on shared host'
        short=[v['client_ms'] for q in req for v in q.get('short_commands',[])]
        if short:r['short_command_median_ms']=statistics.median(short)
        cpu=[json.loads(q['cpu']['stdout']) for q in req if 'cpu' in q]
        if cpu:
            r['guest_cpu_work_wall_ms']=statistics.median(q['wall_ms'] for q in cpu)
            r['guest_cpu_work_cpu_ms']=statistics.median(q['cpu_ms'] for q in cpu)
        io=[json.loads(q['io']['stdout']) for q in req if 'io' in q]
        if io:r['guest_write_fsync_ms']=statistics.median(q['write_fsync_ms'] for q in io)
        resume=[q['resume_to_verified_ms'] for q in req if 'resume_to_verified_ms' in q]
        if resume:r['resume_to_verified_median_ms']=statistics.median(resume)
    rows.append(r)
(D/'summary.json').write_text(json.dumps(dict(qualification='Pilot; no ranking without exclusive host, matching conditions and sufficient samples',rows=rows),indent=2))
keys=sorted({k for r in rows for k in r})
with (D/'summary.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
paired=[]
conditions=('round','case','mode','count','rate','limit','requests','entropy','different')
for r in rows:
    baseline=next((b for b in rows if b['product']=='cube' and all(b.get(k)==r.get(k) for k in conditions)),None)
    if baseline is None:continue
    for metric in ('command_ms','ready_median_ms','short_command_median_ms','guest_cpu_work_wall_ms','guest_cpu_work_cpu_ms','guest_write_fsync_ms','resume_to_verified_median_ms','completed_tasks_per_second'):
        if metric in r and baseline.get(metric):
            paired.append(dict(**{k:r.get(k) for k in conditions},product=r['product'],metric=metric,value=r[metric],cube_value=baseline[metric],relative_percent=(r[metric]/baseline[metric]-1)*100,qualification='pilot_not_a_ranking'))
if paired:
    with (D/'paired.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
print(json.dumps(dict(results=len(rows),failed=sum(r['returncode']!=0 for r in rows),output=str(D)),indent=2))
