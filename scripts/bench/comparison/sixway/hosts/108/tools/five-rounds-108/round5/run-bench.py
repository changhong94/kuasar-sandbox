import json,subprocess,time,datetime
from pathlib import Path
M=Path('/opt/bench108');T=M/'tools/five-rounds-108/round5';R=M/'results/five-rounds-108/round5';PYTHON=str(M/'venv/bin/python')
for lang in ['node','ruby']:
 cfg=json.loads((T/(lang+'.json')).read_text());ctl=cfg['kuasar-mlink']['ctl'];other='ruby' if lang=='node' else 'node';othercfg=json.loads((T/(other+'.json')).read_text())
 # Only owned isolated test templates are changed.
 with (R/(lang+'-policy-switch.log')).open('w') as log:
  subprocess.run(['nsenter','--net=/run/netns/b108-mlink-lang',*ctl,'template','prewarm','disable',othercfg['kuasar-mlink']['template'],'--wait'],stdout=log,stderr=subprocess.STDOUT,check=True)
  subprocess.run(['nsenter','--net=/run/netns/b108-mlink-lang',PYTHON,str(T/'isolated-prepare.py'),lang],stdout=log,stderr=subprocess.STDOUT,check=True)
  subprocess.run(['nsenter','--net=/run/netns/b108-mlink-lang',PYTHON,str(T/'preflight.py'),lang],stdout=log,stderr=subprocess.STDOUT,check=True)
 with (R/(lang+'-bench.log')).open('w') as log:
  subprocess.run([PYTHON,str(T/'bench.py'),str(T/(lang+'.json')),'--out',str(R/lang)],stdout=log,stderr=subprocess.STDOUT,check=True)
 print(lang,(R/lang/'summary.json').read_text(),flush=True)
