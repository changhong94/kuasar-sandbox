from pathlib import Path
import json,subprocess,shutil,time
B=Path('/home/hong/src/research/refill-scale-fixed-113');PY='/home/hong/src/research/python-latest-113/venv/bin/python'
assert (B/'unit-tests.log').read_text().strip().endswith('OK')
assert '13 passed; 0 failed' in (B/'test-final-net.log').read_text()
assert 'Finished `release`' in (B/'build-final-ch.log').read_text()
assert '1 passed; 0 failed' in (B/'test-final-fork.log').read_text()
assert '1 passed; 0 failed' in (B/'test-final-snapshot.log').read_text()
assert 'Finished `release`' in (B/'build-final-sandbox.log').read_text()
for n in (8,16,32,64):
 b=B/str(n);(b/'before').mkdir(exist_ok=True);shutil.copyfile(B/'unit-tests.log',b/'unit-tests.log')
 (b/'load-before.json').write_text(json.dumps({'time':time.time(),'load':Path('/proc/loadavg').read_text(),'meminfo':Path('/proc/meminfo').read_text()}))
 print('START WORKERS',n,flush=True)
 subprocess.run(['python3',str(b/'deploy.py')],check=True)
 for name in ('prepare.py','burst256.py'):
  subprocess.run(['nsenter','--net=/run/netns/py113-fork',PY,str(b/name)],check=True)
 r=json.loads((b/'results/burst256/kuasar-fork/result.json').read_text())
 assert r['print']['completed']==256 and r['pool_while_instances_retained']['ready']==64 and r['pool_while_instances_retained']['assigned']==256
 shutil.copyfile('/var/log/bench-python113-refill-scale-fixed.log',b/'host-all.log')
 subprocess.run(['python3',str(b/'analyze.py'),str(b)],check=True)
 print('FINISHED WORKERS',n,flush=True)
(B/'formal-complete.json').write_text(json.dumps({'complete':True,'workers':[8,16,32,64],'time':time.time()}))
