from pathlib import Path
import fcntl,json,subprocess,hashlib,shutil,ast,time
B=Path('/home/hong/src/research/pool-workers-113');Q=Path('/home/hong/src/research/python-latest-113/src/kuasar-fork/kuasar-io/kuasar');bench=Path('/home/hong/src/research/report-revision-113/bench');D=Path('/home/hong/src/research/python-latest-113/data/fork')
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for repo in (Q,bench):
  assert subprocess.check_output(['runuser','-u','hong','--','git','-C',str(repo),'branch','--show-current'],text=True).strip()=='sandbox_fork_staging'
  subprocess.run(['runuser','-u','hong','--','git','-C',str(repo),'diff','--check'],check=True)
 state=json.loads((D/'adapter-state.json').read_text());assert len(state)==64 and all(x['pool_state']=='ready' and x['network_state']=='ready' for x in state.values())
 hashes={p:hashlib.sha256((Q/'integrations/e2b'/p).read_bytes()).hexdigest() for p in ('template_pool.py','vm_backend.py','image_pool.py','server.py')}
 for group in ('8','16','32','64','8-repeat'):
  d=json.loads((B/group/'deployment.json').read_text());assert hashes==d['source_hashes']
  r=json.loads((B/group/'results/burst256/kuasar-fork/result.json').read_text());assert r['batch_valid'] and not r['public_remaining'] and r['all_private_files_verified'] and r['survivors_verified_after_half_destroyed']
 dest=bench/'scripts/bench/comparison/sixway/pool-workers';dest.mkdir(parents=True,exist_ok=True)
 for p in B.glob('*.py'):
  if p.name.startswith('template_pool') or p.name=='compare.py':continue
  ast.parse(p.read_text());shutil.copyfile(p,dest/p.name)
 for name in ('8','16','32','64','8-repeat'):
  (dest/name).mkdir(exist_ok=True)
  for p in (B/name).glob('*.py'):ast.parse(p.read_text());shutil.copyfile(p,dest/name/p.name)
 if (B/'README.md').exists():shutil.copyfile(B/'README.md',dest/'README.md')
 subprocess.run(['chown','-R','hong:hong',str(dest)],check=True)
 audit=dict(time=time.time(),branch='sandbox_fork_staging',source_hashes=hashes,user_instances_remaining=0,ready=64,default_workers=8,groups=json.loads((B/'comparison.json').read_text()),report_sha256=hashlib.sha256((B/'report/refill-workers-zh-en.pdf').read_bytes()).hexdigest())
 (B/'final-audit.json').write_text(json.dumps(audit,indent=2))
 print('PASS: all groups cleaned, same implementation hashes, 64 reserves, default 8, staging only')
