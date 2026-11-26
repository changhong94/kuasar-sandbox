from pathlib import Path
import fcntl,subprocess,json,time,hashlib,sys
B=Path('/home/hong/src/research/sevenway-current-20261126/six');O=Path('/home/hong/src/research/report-revision-113');Q=Path('/home/hong/src/research/python-latest-113/src/kuasar-fork/kuasar-io/kuasar');PY='/home/hong/src/research/python-latest-113/venv/bin/python'
while not (B/'paced-complete.json').exists():time.sleep(10)
assert 'OK' in (B/'startup-parallel-tests.log').read_text()
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 # Re-read capacity configuration at the dedicated Cubelet's startup.
 # Live scheduler evidence showed the old 176-vCPU quota was still applied.
 subprocess.run(['nsenter','--net=/run/netns/bench113',PY,'-c',"import sys,json;from pathlib import Path;sys.path.insert(0,'"+str(B/'tools')+"');from startup import setup;c,S=setup('cube',json.loads(Path('"+str(B/'tools/config.json')+"').read_text()));p=S.list();ids=[];\nwhile p.has_next:ids.extend(x.sandbox_id for x in p.next_items())\nassert not ids,ids"],check=True)
 subprocess.run(['systemctl','restart','cube-sandbox-cubelet'],check=True)
 time.sleep(15)
 started=time.time_ns()
 with (B/'parallel-startup-reset.log').open('w') as f:
  subprocess.run(['nsenter','--net=/run/netns/py113-fork',PY,str(O/'reset-owned-fork.py')],stdout=f,stderr=subprocess.STDOUT,check=True)
  subprocess.run(['nsenter','--net=/run/netns/py113-fork',PY,'-c',"import sys,json;from pathlib import Path;sys.path.insert(0,'"+str(B/'tools')+"');from pool_gate import wait;c=json.loads(Path('"+str(B/'tools/config.json')+"').read_text())['kuasar-fork'];print(json.dumps(wait(c,64,600)))"],stdout=f,stderr=subprocess.STDOUT,check=True)
 events=Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json.pool-events.jsonl').read_bytes()
 (B/'preparation/fork-startup-events.jsonl').write_bytes(events)
 (B/'parallel-startup-preparation.json').write_text(json.dumps({'start_unix_ns':started,'end_unix_ns':time.time_ns(),'workers':8,'ready':64,'source_sha256':hashlib.sha256((Q/'integrations/e2b/template_pool.py').read_bytes()).hexdigest()}))
 # Preserve earlier runtime-equivalent cases, but report only the deployed version.
 prior=B/'predeploy-fork-batches';prior.mkdir()
 for interval in (0,10,25,50,100):
  for product in ('kuasar-fork','cube'):
   (B/'results/paced'/str(interval)/product).rename(prior/(str(interval)+'-'+product))
 (B/'paced-complete.json').rename(prior/'paced-complete.json')
with (B/'paced-parallel-startup.log').open('w') as f:subprocess.run(['python3',str(B/'run_paced.py')],stdout=f,stderr=subprocess.STDOUT,check=True)
(B/'parallel-startup-deployed.json').write_text(json.dumps({'time':time.time(),'all_five_fork_batches_retested':True,'workers':8}))
