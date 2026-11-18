from pathlib import Path
import fcntl,json,os,secrets,subprocess as sp,time
B=Path('/home/hong/src/research/report-revision-113')
P=Path('/home/hong/src/research/python-latest-113/deploy/fork')
D=Path('/home/hong/src/research/python-latest-113/data/fork')
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 private=B/'private';private.mkdir(mode=0o700,exist_ok=True)
 run=Path('/run/bench-revision113');run.mkdir(mode=0o700,exist_ok=True)
 store=run/'store.sock';cache=run/'cache.sock';health=run/'health.sock'
 def save(name,text):
  p=private/name;p.write_text(text);p.chmod(0o600);return p
 sc=save('store.yaml',f'listen: unix://{store}\nbackend: fs\nfs:\n  root: {B}/store\n  verify_content_key: true\n')
 cc=save('cache.yaml',f'''mode: tiered
listen: unix://{cache}
health_listen: unix://{health}
freq:
  disable_eviction: true
tiers:
  - type: embedded
    rocks:
      path: {B}/rocks-cache
      disk_bytes: 4GiB
      mem_ratio: 0.1
      statistics: true
      direct_reads: true
origin:
  type: store
  store:
    endpoint: unix://{store}
    pool: 4
''')
 mc=private/'manifest.yaml'
 if not mc.exists():
  save('manifest.yaml',f'''manifest:
  key: "{secrets.token_hex(32)}"
  verify_content: true
store:
  endpoint: unix://{store}
cache:
  endpoint: unix://{cache}
crypto:
  chunk: aes
  manifest: aes
chunker:
  mode: cdc
''')
 if not (B/'store').exists():
  sp.run([str(B/'bin/store-ctl'),'init','--config',str(sc),'--generation','G1'],check=True,stdout=sp.DEVNULL)
 for kind,config in [('store',sc),('cache',cc)]:
  unit='bench-revision113-'+kind
  if sp.run(['systemctl','is-active','--quiet',unit]).returncode:
   sp.run(['systemctl','reset-failed',unit],stdout=sp.DEVNULL,stderr=sp.DEVNULL)
   sp.run(['systemd-run','--unit',unit,'--property=MemoryMax=8G','/bin/bash','-c','exec "$1" serve --config "$2"','bash',str(B/'bin'/(kind+'-ctl')),str(config)],check=True)
 for _ in range(100):
  if sp.run([str(B/'bin/cache-ctl'),'ping','--endpoint','unix://'+str(health)],stdout=sp.DEVNULL,stderr=sp.DEVNULL).returncode==0:break
  time.sleep(.1)
 else:raise TimeoutError('private RocksDB cache readiness')
 # Reuse the already-reviewed owned-service drain; never operate on mlink or unrelated VMs.
 reset=Path('/home/hong/src/research/sixway-aligned-20261117/tools/reset-fork.py').read_text()
 assert "mode='fork';capacity=2;" in reset
 reset=reset.replace("mode='fork';capacity=2;","mode='fork';capacity=64;")
 (B/'reset-owned-fork.py').write_text(reset)
 start=time.monotonic_ns()
 sp.run(['nsenter','--net=/run/netns/py113-fork','env','POOL_RESET_STOPPED=1','python3',str(B/'reset-owned-fork.py')],check=True)
 drop=Path('/etc/systemd/system/bench-python113-fork.service.d/zz-report-revision.conf')
 if drop.exists():raise RuntimeError('deployment override already exists; inspect before replacing')
 drop.write_text('[Service]\nEnvironment=E2B_TEMPLATE_POOL_SIZE=64\nEnvironment=E2B_MANIFEST_CONFIG='+str(mc)+'\nEnvironment=E2B_MANIFEST_RAW='+str(B/'bin/manifest-raw')+'\n')
 sp.run(['systemctl','daemon-reload'],check=True)
 sp.run(['systemctl','start','bench-python113-fork'],check=True)
 code="import sys,json;sys.path.insert(0,'/home/hong/src/research/ready-regression-113/tools');from pool_gate import wait;c=json.load(open('/home/hong/src/research/ready-regression-113/tools/config.json'));print(json.dumps(wait(c['kuasar-fork'],capacity=64,timeout=600)))"
 state=json.loads(sp.check_output(['nsenter','--net=/run/netns/py113-fork','python3','-c',code],text=True))
 (B/'deployment.json').write_text(json.dumps({'pool':state,'elapsed_ms':(time.monotonic_ns()-start)/1e6,'cache_blob_capacity_override':False,'cache_statistics':True},indent=2))
 print('owned fork pool ready: 64 slots')
