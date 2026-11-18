from pathlib import Path
import json,subprocess,time
B=Path('/home/hong/src/research/report-review-113');O=Path('/home/hong/src/research/report-revision-113');PY='/home/hong/src/research/python-latest-113/venv/bin/python'
while not (B/'validation-batches-complete.json').exists():time.sleep(10)
for name in ['carrier_accounting','runtime_manifest','source_manifest']:
 p=B/(name+'.py')
 if not p.exists():p.write_text((O/(name+'.py')).read_text().replace(str(O),str(B)))
for script in ['analyze_pool.py','analyze_failures.py','carrier_accounting.py','runtime_manifest.py','final_audit.py']:
 print('START',script,flush=True)
 with (B/(script+'.log')).open('w') as f:subprocess.run([PY,str(B/script)],stdout=f,stderr=subprocess.STDOUT,check=True)
 print('DONE',script,flush=True)
# Avoid unsafe-root Git ownership overrides; provenance reads as repository owner.
subprocess.run(['runuser','-u','hong','--',PY,str(B/'source_manifest.py')],check=True)
(B/'analysis-complete.json').write_text(json.dumps({'time':time.time(),'ready_for_pdf':True}))
