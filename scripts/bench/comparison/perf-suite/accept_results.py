"""Index successful validated pilot cases; retain all failed/superseded evidence."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('directories',nargs='+');p.add_argument('--output',required=True);a=p.parse_args()
selected={};excluded=[]
keys=('case','product','round','mode','count','rate','limit','requests','entropy','different')
for directory in a.directories:
    d=Path(directory);validation=json.loads((d/'validation.json').read_text())
    valid={c['name'] for c in validation['checks'] if c['valid']}
    for r in json.loads((d/'results.json').read_text()):
        entry=dict(r,directory=str(d/r['name']))
        if r['name'] not in valid:excluded.append(dict(entry,reason='failed_validation'));continue
        key=tuple(r.get(k) for k in keys)
        if key in selected:excluded.append(dict(selected[key],reason='superseded_by_validated_rerun'))
        selected[key]=entry
result=dict(functional_cases=len(selected),selected=list(selected.values()),excluded=excluded,formal_performance_valid=False,
            note='Only functional/data-integrity acceptance. Shared host and small samples do not support product ranking.')
Path(a.output).write_text(json.dumps(result,indent=2));print(json.dumps(dict(functional_cases=len(selected),excluded=len(excluded),output=a.output)))
