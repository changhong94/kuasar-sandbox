"""Verify artifacts before using them in a report; never change source results."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('directory');a=p.parse_args();D=Path(a.directory)
issues=[];checks=[]
for row in json.loads((D/'results.json').read_text()):
    out=D/row['name']
    if row['returncode']:issues.append(dict(name=row['name'],error='worker_failed'));continue
    if row['case']=='certificate':
        trials=list(out.glob('trials/*/result.json'))
        reward=(json.loads(trials[0].read_text()).get('verifier_result') or {}).get('rewards',{}).get('reward') if len(trials)==1 else None
        replay=list(out.glob('trials/*/agent/fixed-replay.json'))
        r=json.loads(replay[0].read_text()) if len(replay)==1 else {}
        valid=reward==1 and len(r.get('commands',[]))==14 and r.get('model_calls')==0
        event_files=list(out.glob('trials/*/agent/environment-events.json'))
        events=json.loads(event_files[0].read_text()) if len(event_files)==1 else []
        valid=valid and sum(e['event']=='created' for e in events)==1 and sum(e['event']=='deleted' for e in events)==1
        checks.append(dict(name=row['name'],valid=valid,reward=reward))
        if not valid:issues.append(dict(name=row['name'],error='certificate_gate'))
        continue
    r=json.loads((out/'result.json').read_text());valid=r.get('completed') and not r['owned_remaining']
    if any(not x['success'] for x in r['cleanup']):valid=False
    requests=r['requests']
    if row['case']=='storage':
        digests=[tuple(f['sha256'] for f in json.loads(x['files']['stdout'])['files']) for x in requests]
        content_ok=len(set(digests))==(row['count'] if row.get('different') else 1)
        valid=valid and content_ok
        if not content_ok:issues.append(dict(name=row['name'],error='same_different_content_mismatch'))
    if row['case']=='memory':
        for x in requests:
            events=[json.loads(line) for line in x['memory']['stdout'].splitlines() if line.strip()]
            valid=valid and [e['stage'] for e in events]==['before','allocated_and_written','unmapped','after_5s','after_15s']
    telemetry=out/'telemetry.jsonl'
    if telemetry.exists():
        samples=[json.loads(l) for l in telemetry.read_text().splitlines() if l.strip()]
        valid=valid and bool(samples) and not any('error' in s for s in samples)
    checks.append(dict(name=row['name'],valid=bool(valid),attempts=len(requests),successes=sum(bool(x.get('success')) for x in requests)))
    if not valid and not any(i['name']==row['name'] for i in issues):issues.append(dict(name=row['name'],error='data_or_cleanup_gate'))
result=dict(functional_artifacts_valid=not issues,checks=checks,issues=issues,formal_performance_valid=False,
            limitation='Shared host and small samples; this is a functional/data-integrity audit, not a comparative performance conclusion.')
(D/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if issues:raise SystemExit(1)
