import json, os, secrets, socket, subprocess, tempfile, time, hashlib
from pathlib import Path
B=Path('/home/hong/src/research/report-revision-113')
procs=[]
with tempfile.TemporaryDirectory(prefix='manifest-check-') as td:
 p=Path(td)
 def write(name,data):
  path=p/name;path.write_text(data);path.chmod(0o600);return path
 def call(args):
  r=subprocess.run(list(map(str,args)),capture_output=True,check=True,timeout=60)
  return r.stdout.decode()
 def start(binary, config, sock):
  log=(p/(binary+'.log')).open('wb')
  proc=subprocess.Popen([str(B/'bin'/binary),'serve','--config',str(config)],stdout=log,stderr=log)
  procs.append((proc,log))
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   if proc.poll() is not None: raise RuntimeError(binary+' exited')
   s=socket.socket(socket.AF_UNIX)
   try:s.connect(str(sock));s.close();return
   except OSError:s.close();time.sleep(.05)
  raise TimeoutError(binary)
 store=p/'store.sock';cache=p/'cache.sock';health=p/'health.sock'
 sc=write('store.yaml',f'listen: unix://{store}\nbackend: fs\nfs:\n  root: {p}/objects\n  verify_content_key: true\n')
 cc=write('cache.yaml',f'''mode: tiered
listen: unix://{cache}
health_listen: unix://{health}
stats_interval: off
freq:
  disable_eviction: true
tiers:
  - type: embedded
    rocks:
      path: {p}/rocks
      disk_bytes: 128MiB
      mem_ratio: 0.1
      blob_cache_bytes: 32MiB
      statistics: true
      direct_reads: true
origin:
  type: store
  store:
    endpoint: unix://{store}
    pool: 2
''')
 mc=write('manifest.yaml',f'''manifest:
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
 try:
  call([B/'bin/store-ctl','init','--config',sc,'--generation','G1'])
  start('store-ctl',sc,store);start('cache-ctl',cc,cache)
  source=p/'source.raw'
  with source.open('wb') as f:
   f.write(os.urandom(1<<20));f.seek(8<<20);f.write(b'Q'*(1<<20));f.truncate(16<<20)
  raw=[B/'bin/manifest-raw','--manifest-config',mc]
  published=json.loads(call([*raw,'store',source]))
  duplicate=json.loads(call([*raw,'store',source]))
  def info():return json.loads(call([B/'bin/cache-ctl','info','--endpoint','unix://'+str(health),'--json']))
  before=info()
  results=[]
  digest=hashlib.sha256(source.read_bytes()).hexdigest()
  for i in range(2):
   target=p/f'restored-{i}'
   result=json.loads(call([*raw,'load',published['manifest'],target]))
   assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
   assert target.stat().st_blocks*512 < target.stat().st_size
   results.append(result)
   time.sleep(.1)
  after=info()
  assert duplicate['stats']['DedupChunks'] > 0
  assert published['stats']['CompressedChunks'] > 0
  evidence=dict(success=True,sparse=True,encrypted_manifest=True,integrity_verified=True,digest=digest,publication=published,duplicate=duplicate,restores=results,cache_before=before,cache_after=after)
  (B/'manifest-roundtrip.json').write_text(json.dumps(evidence,indent=2))
  print(json.dumps({'success':True,'logical_bytes':source.stat().st_size,'restore_ms':[r['elapsed_ms'] for r in results],'dedup_chunks':duplicate['stats']['DedupChunks']}))
 finally:
  for proc,log in reversed(procs):
   proc.terminate()
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
   log.close()
