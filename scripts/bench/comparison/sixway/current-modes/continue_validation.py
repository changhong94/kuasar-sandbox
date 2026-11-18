"""Run the next independent batches only after all formal startup rows pass."""
import json,subprocess,time,sys,fcntl
from pathlib import Path
B=Path('/home/hong/src/research/report-revision-113');T=B/'tools'
PYTHON='/home/hong/src/research/python-latest-113/venv/bin/python'

def run(name,argv):
 print('START',name,flush=True)
 (B/'validation-progress.json').write_text(json.dumps({'phase':name,'started_unix':time.time()}))
 with (B/(name+'.log')).open('w') as log:
  subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
 print('DONE',name,flush=True)

while not (B/'results/matrix/complete.json').exists():time.sleep(10)
folders=list((B/'results/matrix').glob('*/*/*/50.json'))
assert len(folders)==36,len(folders)
for last in folders:
 for name in ['warmup']+[f'{i:02d}' for i in range(1,51)]:
  row=json.loads((last.parent/(name+'.json')).read_text())
  assert row['success'] and row['destroyed'],last.parent/name
run('live-formal',['nsenter','--net=/run/netns/py113-fork',PYTHON,str(B/'live_fork.py'),'--samples','50','--out',str(B/'results/live-formal')])
run('analyze-live',[PYTHON,str(B/'analyze_live.py'),str(B/'results/live-formal')])
run('summarize-startup',[PYTHON,str(B/'summarize_modes.py'),str(B)])
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 run('resource-python-prepare',[PYTHON,str(T/'switch-language.py'),str(T/'config.json'),'python',str(B/'results/preparation/resources-python')])
run('resource-full',[PYTHON,str(T/'run_full.py')])
run('snapshots-formal',[PYTHON,str(B/'snapshot_bench.py')])
(B/'validation-batches-complete.json').write_text(json.dumps({'completed_unix':time.time()}))
