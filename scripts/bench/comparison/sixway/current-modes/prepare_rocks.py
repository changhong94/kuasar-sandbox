from pathlib import Path
import fcntl,json,os,re,sqlite3,subprocess as sp,time
B=Path('/home/hong/src/research/report-revision-113')
CACHE=B/'bin/cache-ctl'
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 settings={'kuasar-fork':{'endpoint':'unix:///run/bench-revision113/health.sock','service':'bench-revision113-cache','backend':'rocksdb','direct_reads':True}}
 for product,afile,unit in [('kuasar-off','/home/hong/deploy/comparison/kuasar-state/access.json','kuasar-comparison-node'),('kuasar-uffd','/home/hong/deploy/private-pilot/uffd-state/access.json','bench-private-uffd-serve')]:
  access=json.loads(Path(afile).read_text());work=Path(access['work_dir'])
  with sqlite3.connect((work/'lib/node-ctl.db').as_uri()+'?mode=ro',uri=True) as db:
   assert db.execute('SELECT COUNT(*) FROM sandboxes').fetchone()[0]==0
  original=work/'manifest.yaml';backup=B/'private'/(product+'-manifest-original.yaml')
  if not backup.exists():backup.write_bytes(original.read_bytes());backup.chmod(0o600)
  text=backup.read_text()
  old=re.search(r"cache:.*endpoint:\s*['\"]?([^'\" },]+)",text)[1]
  origin=re.search(r"store:.*endpoint:\s*['\"]?([^'\" },]+)",text)[1]
  suffix=product.rsplit('-',1)[-1];sock='/run/bench-revision113/'+suffix
  config=B/'private'/(suffix+'-cache.yaml')
  config.write_text(f'''mode: tiered
listen: unix://{sock}.sock
health_listen: unix://{sock}-health.sock
freq:
  disable_eviction: true
tiers:
  - type: embedded
    rocks:
      path: {B}/rocks-{suffix}
      disk_bytes: 4GiB
      mem_ratio: 0.1
      statistics: true
      direct_reads: true
origin:
  type: store
  store:
    endpoint: '{origin}'
    pool: 4
''');config.chmod(0o600)
  service='bench-revision113-cache-'+suffix
  if sp.run(['systemctl','is-active','--quiet',service]).returncode:
   sp.run(['systemctl','reset-failed',service],stdout=sp.DEVNULL,stderr=sp.DEVNULL)
   sp.run(['systemd-run','--unit',service,'--property=MemoryMax=8G','/bin/bash','-c','exec "$1" serve --config "$2"','bash',str(CACHE),str(config)],check=True)
  for _ in range(100):
   if sp.run([str(CACHE),'ping','--endpoint','unix://'+sock+'-health.sock'],stdout=sp.DEVNULL,stderr=sp.DEVNULL).returncode==0:break
   time.sleep(.1)
  else:raise TimeoutError(service)
  original.write_text(text.replace(old,'unix://'+sock+'.sock'))
  with original.open('rb') as f:os.fsync(f.fileno())
  settings[product]={'endpoint':'unix://'+sock+'-health.sock','service':service,'backend':'rocksdb','direct_reads':True}
 (B/'remote-cache.json').write_text(json.dumps(settings,indent=2))
 print('RocksDB instrumentation endpoints configured; no memory-hit requirement')
