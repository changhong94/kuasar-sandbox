from pathlib import Path
import argparse,json,subprocess,shutil,time
B=Path('/home/hong/src/research/pool-workers-113');PY='/home/hong/src/research/python-latest-113/venv/bin/python'
assert (B/'unit-tests.log').read_text().strip().endswith('OK')
parser=argparse.ArgumentParser();parser.add_argument('--groups',nargs='+',default=['8','16','32','64']);args=parser.parse_args()
for n in args.groups:
 assert n in ('8','16','32','64','8-repeat')
 b=B/str(n);(b/'before').mkdir(exist_ok=True);shutil.copyfile(B/'unit-tests.log',b/'unit-tests.log')
 (b/'load-before.json').write_text(json.dumps({'time':time.time(),'load':Path('/proc/loadavg').read_text(),'meminfo':Path('/proc/meminfo').read_text()}))
 print('START WORKERS',n,flush=True)
 subprocess.run(['python3',str(b/'deploy.py')],check=True)
 for name in ('prepare.py','burst256.py'):
  run=subprocess.run(['nsenter','--net=/run/netns/py113-fork',PY,str(b/name)])
  if name=='prepare.py':run.check_returncode()
 r=json.loads((b/'results/burst256/kuasar-fork/result.json').read_text())
 assert r['batch_valid'] and not r['public_remaining']
 assert r['pool_while_instances_retained']['workers']==int(n.split('-')[0]) and r['pool_while_instances_retained']['ready']==64
 with (b/'host-all.log').open('w') as f:
  subprocess.run(['journalctl','-u','bench-python113-fork','--since','@'+str(r['start_unix_ns']//10**9-1),'--until','@'+str(r['end_unix_ns']//10**9+1),'-o','cat'],stdout=f,check=True)
 if r['print']['completed']==256:subprocess.run(['python3',str(b/'analyze.py'),str(b)],check=True)
 else:print('PARTIAL SUCCESS',n,r['print']['completed'],flush=True)
 print('FINISHED WORKERS',n,flush=True)
(B/('complete-'+'-'.join(args.groups)+'.json')).write_text(json.dumps({'complete':True,'groups':args.groups,'time':time.time()}))
