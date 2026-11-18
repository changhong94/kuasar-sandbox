from pathlib import Path
import fcntl,json,os,subprocess,time,hashlib
B=Path('/home/hong/src/research/pool-workers-113/32');OLD=Path('/home/hong/src/research/report-revision-113');Q=Path('/home/hong/src/research/python-latest-113/src/kuasar-fork/kuasar-io/kuasar');D=Path('/home/hong/src/research/python-latest-113/data/fork')
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert subprocess.check_output(['git','-C',str(Q),'branch','--show-current'],text=True).strip()=='sandbox_fork_staging'
 tests=B/('unit-tests-final.log' if (B/'unit-tests-final.log').exists() else 'unit-tests.log')
 assert tests.read_text().strip().endswith('OK')
 records=json.loads((D/'adapter-state.json').read_text());assert all(r.get('pool_state')=='ready' for r in records.values()) and len(records)==64
 (B/'before/deployment.json').write_text(json.dumps({'records':len(records),'source':str(Q),'head':subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()},indent=2))
 subprocess.run(['nsenter','--net=/run/netns/py113-fork','python3',str(OLD/'reset-owned-fork.py')],env={**os.environ,'POOL_RESET_STOPPED':'1'},check=True)
 drop=Path('/etc/systemd/system/bench-python113-fork.service.d/zzzz-parallel-refill.conf')
 drop.write_text('[Service]\nEnvironment=E2B_TEMPLATE_POOL_WORKERS=32\nLogRateLimitIntervalSec=0\n')
 subprocess.run(['systemctl','daemon-reload'],check=True)
 started=time.monotonic_ns();subprocess.run(['systemctl','start','bench-python113-fork'],check=True)
 code="import sys,json;sys.path.insert(0,"+repr(str(OLD/'tools'))+");from pool_gate import wait;c=json.load(open("+repr(str(OLD/'tools/config.json'))+"));print(json.dumps(wait(c['kuasar-fork'],64,600)))"
 gate=json.loads(subprocess.check_output(['nsenter','--net=/run/netns/py113-fork','python3','-c',code],text=True))
 assert gate['state']['capacity_scope']=='unclaimed_reserves'
 (B/'deployment.json').write_text(json.dumps({'ready':gate,'service_to_ready_ms':(time.monotonic_ns()-started)/1e6,'source_hashes':{n:hashlib.sha256((Q/'integrations/e2b'/n).read_bytes()).hexdigest() for n in ['template_pool.py','vm_backend.py','image_pool.py','server.py']}},indent=2))
print('DEPLOYED: 64 unclaimed reserves, independent of running instance count')
