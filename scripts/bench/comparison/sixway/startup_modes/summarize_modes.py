import csv
import json
import math
from pathlib import Path
import statistics
import sys

base=Path(sys.argv[1])
summary=[]
def add(product,language,mode,metric,values):
    values=sorted(values)
    assert len(values)==10
    summary.append({'product':product,'language':language,'mode':mode,'metric':metric,
        'n':10,'median_ms':statistics.median(values),
        'p95_ms':values[math.ceil(.95*len(values))-1],
        'p99_ms':values[math.ceil(.99*len(values))-1],'max_ms':values[-1]})
for path in sorted((base/'results/matrix').glob('*/*/*/10.json')):
    mode=path.parent.name;product=path.parent.parent.name;language=path.parent.parent.parent.name
    rows=[json.loads((path.parent/f'{i:02d}.json').read_text()) for i in range(1,11)]
    assert all(r['success'] and r['destroyed'] for r in rows)
    for metric in ['api_ms','ready_ms','print_ms','delete_ms']:
        add(product,language,mode,metric,[r[metric] for r in rows])
    if mode.startswith('local_'):
        add(product,language,mode,'cache_condition_ms',[r['cache_preparation']['preparation_ms'] for r in rows])
live=json.loads((base/'results/live-formal/analyzed.json').read_text())
for language,group in live.items():
    for metric,s in group['metrics'].items():
        summary.append({'product':'kuasar-fork','language':language,'mode':'live_parent_fork',
            'metric':metric,'n':s['n'],'median_ms':s['median'],'p95_ms':s['p95'],
            'p99_ms':s['p99'],'max_ms':s['max']})
(base/'summary.json').write_text(json.dumps(summary,indent=2))
with (base/'summary.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
print('Summary rows',len(summary))
