from pathlib import Path
import json
R=Path('/home/hong/src/research/sixway-aligned-20261117/results')
out={'phase':json.loads((R/'progress.json').read_text())}
for name,pat in [('timing','[1-5]-*.json'),('timing/storage','[1-3]-*.json'),('growth','*.json'),('arrays','*.json')]:
 rows=[json.loads(p.read_text()) for p in (R/name).glob(pat)]
 out[name]={'records':len(rows),'passed':sum(bool(d.get('success') or d.get('verified')==50) and not d.get('owned') and not d.get('remaining') and not d.get('owned_remaining') for d in rows),'errors':[d.get('error') for d in rows if d.get('error')]}
print(json.dumps(out))
