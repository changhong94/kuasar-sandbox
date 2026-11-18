from pathlib import Path
import json,hashlib,shutil
B=Path('/home/hong/src/research/sixway-aligned-20261117');R=B/'results/startup';first=min(json.loads(p.read_text())['start_unix_ns'] for p in R.glob('[0-9][0-9]-*.json'));dest=R/'tools';dest.mkdir(exist_ok=True);out={}
for name in ['startup.py','pool_gate.py','config.json']:
 p=B/'tools'/name;assert p.stat().st_mtime_ns<first,(name,'changed after execution began')
 shutil.copy2(p,dest/name);out[name]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mtime_ns=p.stat().st_mtime_ns)
(R/'execution-code.json').write_text(json.dumps(dict(first_sample_unix_ns=first,files=out),indent=2));print('Frozen startup code verified predates all samples')
