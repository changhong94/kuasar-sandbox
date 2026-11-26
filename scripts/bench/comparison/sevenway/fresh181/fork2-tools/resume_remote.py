import pathlib,subprocess,time,json,sqlite3,os
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2');T=R/'tools';P='/srv/fork2/bin/python-sdk'
def run(*a):subprocess.run(a,check=True)
def status(s): (R/'status.json').write_text(json.dumps({'phase':s,'updated_ns':time.time_ns(),'complete':False}))
def empty():
 deadline=time.monotonic()+120
 while True:
  with sqlite3.connect('file:/srv/fork2/data/base/node-ctl.db?mode=ro',uri=True)as db:n=db.execute('select count(*) from sandboxes').fetchone()[0]
  if n==0:return
  if time.monotonic()>=deadline:raise TimeoutError('deletion not settled before config transition')
  time.sleep(.05)
empty();private=R/'private';private.mkdir(mode=0o700,exist_ok=True)
cp=pathlib.Path('/srv/fork2/conductor.json');mp=pathlib.Path('/srv/fork2/manifest.json');co=cp.read_bytes();mo=mp.read_bytes()
(private/'conductor.original').write_bytes(co);(private/'manifest.original').write_bytes(mo)
def restart():
 empty();run('systemctl','stop','fork2-conductor','fork2-proxy')
 units=[x.split()[0]for x in subprocess.check_output(['systemctl','list-units','fork2-runner@*','--plain','--no-legend'],text=True).splitlines()if x.startswith('fork2-runner@')]
 if units:run('systemctl','stop',*units)
 run('systemctl','stop','fork2-shared')
 run('systemctl','start','fork2-conductor','fork2-proxy')
try:
 c=json.loads(co);c['checkpoint']['snapshot_target']='location';cp.write_text(json.dumps(c));restart()
 # Local matrix already validated: do not rerun.
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
 cache='/srv/fork2/bin/cache-ctl-sevenway'
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
 subprocess.run(['systemctl','stop','fork2-sevenway-cache'],check=False)
status('remote-finished');print('THIRD_SUITES_COMPLETE',flush=True)
