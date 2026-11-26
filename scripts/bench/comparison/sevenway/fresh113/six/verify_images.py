"""Post-benchmark identity audit in disposable sandboxes, outside timing."""
import fcntl,json,subprocess,sys
from pathlib import Path
B=Path('/home/hong/src/research/sevenway-current-20261126/six');T=B/'tools';cfg=json.loads((T/'config.json').read_text());rows=[]
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for language in ('python','node','ruby'):
  subprocess.run([sys.executable,str(T/'switch-language.py'),str(T/'config.json'),language,str(B/'results/preparation'/('identity-'+language))],check=True)
  for product in ('kuasar-fork','kuasar-mlink','agentenv','cube','kuasar-off','kuasar-uffd'):
   out=B/f'results/image-identity/{language}-{product}.json'
   subprocess.run(['nsenter','--net=/run/netns/'+cfg[product]['netns'],sys.executable,str(T/'preflight_language.py'),str(T/'config.json'),'--language',language,'--product',product,'--out',str(out)],check=True)
   row=json.loads(out.read_text());assert row['success'] and row['destroyed'] and row['no_interpreter_running'];rows.append(row)
 subprocess.run([sys.executable,str(T/'switch-language.py'),str(T/'config.json'),'python',str(B/'results/preparation/identity-restore-python')],check=True)
assert len(rows)==18
for language in ('python','node','ruby'):
 group=[r for r in rows if r['language']==language]
 assert len({r['image_digest'] for r in group})==1
 assert len({r['interpreter_sha256'] for r in group})==1
(B/'image-verification.json').write_text(json.dumps({'all_18_verified':True,'same_interpreter_hash_within_each_language':True,'no_interpreter_running_before_check':True,'rows':rows},indent=2))
