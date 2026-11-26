import fcntl,json,sys,time
from pathlib import Path
B=Path('/home/hong/src/research/sevenway-current-20261126/six');sys.path.insert(0,str(B/'tools'))
from languages import select_language
from startup import setup
from pool_gate import wait
cfg=json.loads((B/'tools/config.json').read_text());rows=[]
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for lang in ['python','node','ruby']:
  c,Sandbox=setup('kuasar-fork',select_language(cfg,lang));wait(c,capacity=64)
  start=time.monotonic_ns();s=Sandbox.create(c['template'],timeout=600,request_timeout=600)
  try:rows.append({'language':lang,'create_with_template_publication_ms':(time.monotonic_ns()-start)/1e6,'application_command':'/bin/sleep infinity','interpreter_started':False})
  finally:s.kill()
  wait(c,capacity=64)
  (B/'fork-template-preparation.json').write_text(json.dumps(rows,indent=2))
  print('PREPARED',lang,flush=True)
