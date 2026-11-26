import pathlib,subprocess,time,json,sqlite3,os
R=pathlib.Path('/home/hong/src/research/sevenway-current-20261126/fork2');T=R/'tools';P='/srv/fork2/bin/python-sdk'
def run(*a):subprocess.run(a,check=True)
def status(s): (R/'status.json').write_text(json.dumps({'phase':s,'updated_ns':time.time_ns(),'complete':False}))
def empty():
 with sqlite3.connect('file:/home/hong/src/research/fork2-control-persistent/node-ctl.db?mode=ro',uri=True)as db:assert db.execute('select count(*) from sandboxes').fetchone()[0]==0
while subprocess.run(['systemctl','is-active','--quiet','fork2-sevenway-second']).returncode==0:time.sleep(3)
assert json.loads((R/'status.json').read_text())['phase']=='second-suites-finished'
empty();private=R/'private';private.mkdir(mode=0o700,exist_ok=True)
cp=pathlib.Path('/srv/fork2/conductor.json');mp=pathlib.Path('/srv/fork2/manifest.json');co=cp.read_bytes();mo=mp.read_bytes()
(private/'conductor.original').write_bytes(co);(private/'manifest.original').write_bytes(mo)
def restart():
 empty();run('systemctl','stop','fork2-conductor','fork2-proxy')
 units=[x.split()[0]for x in subprocess.check_output(['systemctl','list-units','fork2-runner@*','--plain','--no-legend'],text=True).splitlines()if x.startswith('fork2-runner@')]
 if units:run('systemctl','stop',*units)
 run('systemctl','stop','fork2-shared-controller')
 run('systemctl','start','fork2-conductor','fork2-proxy')
try:
 c=json.loads(co);c['checkpoint']['snapshot_target']='location';cp.write_text(json.dumps(c));restart()
 status('snapshot-local-warm-cold');run(P,'-u',str(T/'snapshot_modes.py'),'local')
 empty();sock=pathlib.Path('/run/fork2-sevenway-cache');sock.mkdir(mode=0o700,exist_ok=True)
 cacheconf=private/'cache.yaml';cacheconf.write_text(f'''mode: tiered
listen: unix://{sock}/cache.sock
health_listen: unix://{sock}/health.sock
freq:
  disable_eviction: true
tiers:
  - type: embedded
    rocks:
      path: {R}/rocksdb
      disk_bytes: 4GiB
      mem_ratio: 0.1
      statistics: true
      direct_reads: true
origin:
  type: store
  store:
    endpoint: 127.0.0.1:19212
    pool: 4
''')
 cache='/home/hong/src/research/report-revision-113/bin/cache-ctl'
 run('systemd-run','--unit=fork2-sevenway-cache','--collect','--property=MemoryMax=8G',cache,'serve','--config',str(cacheconf))
 for _ in range(100):
  if subprocess.run([cache,'ping','--endpoint','unix://'+str(sock/'health.sock')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:break
  time.sleep(.1)
 else:raise TimeoutError('dedicated RocksDB cache')
 m=json.loads(mo);m['cache']['endpoint']='unix://'+str(sock/'cache.sock');mp.write_text(json.dumps(m))
 c['checkpoint']['snapshot_target']='manifest';cp.write_text(json.dumps(c));restart()
 status('snapshot-chunked-remote');run(P,'-u',str(T/'snapshot_modes.py'),'remote')
finally:
 empty();cp.write_bytes(co);mp.write_bytes(mo);restart()
 run('systemctl','stop','fork2-sevenway-cache')
status('third-suites-finished');print('THIRD_SUITES_COMPLETE',flush=True)
