"""Finish audits only after the serialized measured batches complete."""
from pathlib import Path
import json,subprocess,time
B=Path('/home/hong/src/research/report-revision-113');PY='/home/hong/src/research/python-latest-113/venv/bin/python'
while not (B/'validation-batches-complete.json').exists():time.sleep(10)
for name in ['read_resource_suite','carrier_accounting','analyze_pool','nested_recovery','verify_images','pool_memory']:
 print('START',name,flush=True)
 (B/'post-validation-progress.json').write_text(json.dumps({'phase':name,'started_unix':time.time()}))
 with (B/(name+'.log')).open('w') as log:subprocess.run([PY,str(B/(name+'.py'))],stdout=log,stderr=subprocess.STDOUT,check=True)
 print('DONE',name,flush=True)
(B/'all-validation-complete.json').write_text(json.dumps({'completed_unix':time.time()}))
