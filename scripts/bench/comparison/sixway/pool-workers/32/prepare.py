from pathlib import Path
import fcntl,json,sys,time
B=Path('/home/hong/src/research/pool-workers-113/32');T=Path('/home/hong/src/research/report-revision-113/tools');sys.path.insert(0,str(T))
from startup import setup
from languages import select_language
from pool_gate import wait
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 cfg=select_language(json.loads((T/'config.json').read_text()),'python');c,S=setup('kuasar-fork',cfg)
 wait(c,64,600);start=time.monotonic_ns();s=S.create(c['template'],timeout=600,request_timeout=600)
 try:row={'image_digest':cfg['_image_digest'],'template_prepare_publish_first_create_ms':(time.monotonic_ns()-start)/1e6,'interpreter_started':False}
 finally:s.kill()
 row['pool']=wait(c,64,600)
 (B/'preparation.json').write_text(json.dumps(row,indent=2))
 print('Prepared Python image without starting its interpreter')
