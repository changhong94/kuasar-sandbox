import os,sys,json,subprocess as sp,fcntl
from pathlib import Path
B=Path('/home/hong/src/research/sixway-languages-20261117');T=B/'tools';C=T/'config.json';O=B/'results/matrix';O.mkdir(exist_ok=False)
sys.path.insert(0,str(T))
from languages import PRODUCTS,select_language
os.environ['SIXWAY_ROOT']=str(B)
def run(args):
 print('RUN',*map(str,args),flush=True);sp.run(list(map(str,args)),check=True)
for lang in ['python','node','ruby']:
 c=select_language(json.loads(C.read_text()),lang)
 with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  run([sys.executable,T/'switch-language.py',C,lang,O/'preparation'/lang])
  proofs=[]
  for product in PRODUCTS:
   target=O/'preflight'/f'{lang}-{product}.json'
   run(['nsenter','--net=/run/netns/'+c[product]['netns'],sys.executable,T/'preflight_language.py',C,'--language',lang,'--product',product,'--out',target])
   proofs.append(json.loads(target.read_text()))
  assert len({(p['version'],p['interpreter_sha256']) for p in proofs})==1,proofs
 run([sys.executable,T/'startup.py',C,'--language',lang,'--out',O/lang])
 run([sys.executable,T/'summarize_startup.py','--config',C,'--language',lang,'--input',O/lang,'--out',O/lang])
 with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for product in PRODUCTS:
   run(['nsenter','--net=/run/netns/'+c[product]['netns'],sys.executable,T/'validate-survivors.py',product,lang])
 print('LANGUAGE_COMPLETE',lang,flush=True)
(O/'languages-summary.json').write_text(json.dumps({l:json.loads((O/l/'summary.json').read_text()) for l in ['python','node','ruby']},indent=2))
