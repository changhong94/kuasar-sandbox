from pathlib import Path
import json,subprocess,hashlib,fcntl,shutil,ast,time
B=Path('/home/hong/src/research/refill-scale-fixed-113');F=Path('/home/hong/src/research/python-latest-113');bench=Path('/home/hong/src/research/report-revision-113/bench')
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for path,previous in json.loads((B/'source-before.json').read_text()).items():
  args=['runuser','-u','hong','--','git','-C',path]
  assert subprocess.check_output(args+['branch','--show-current'],text=True).strip()=='sandbox_fork_staging'
  assert subprocess.check_output(args+['rev-parse','HEAD'],text=True).strip()==previous['head']
  assert hashlib.sha256(subprocess.check_output(args+['diff'])).hexdigest()==previous['diff_sha256']
 state=json.loads((F/'data/fork/adapter-state.json').read_text());assert len(state)==64 and all(x['pool_state']=='ready' and x['network_state']=='ready' for x in state.values())
 assert 'E2B_TEMPLATE_POOL_WORKERS=8' in Path('/etc/systemd/system/bench-python113-fork.service.d/zzzz-parallel-refill.conf').read_text()
 for k in ('8','16','32','64'):
  r=json.loads((B/k/'results/burst256/kuasar-fork/result.json').read_text());assert r['print']['completed']==256 and r['failed_requests']==0 and r['batch_valid'] and r['all_private_files_verified'] and r['survivors_verified_after_half_destroyed'] and r['cleanup_quiescence_verified'] and not r['public_remaining']
  assert r['pool_while_instances_retained']['assigned']==256 and r['pool_while_instances_retained']['ready']==64
 bins={}
 for name,built in (('cloud-hypervisor','/home/hong/src/research/sixway-integrated-20261118/ch-target/release/cloud-hypervisor'),('sandboxer','/home/hong/src/research/fork-features-113/target/release/cloud_hypervisor')):
  h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
  assert h(F/'deploy/fork/bin'/name)==h(built);bins[name]=h(built)
 dest=bench/'scripts/bench/comparison/sixway/refill-scale-fixed';dest.mkdir(parents=True,exist_ok=True)
 assert subprocess.check_output(['runuser','-u','hong','--','git','-C',str(bench),'branch','--show-current'],text=True).strip()=='sandbox_fork_staging'
 for name in ('run.py','report.py','plot_helpers.py','finalize.py','export_csv.py'):
  p=B/name;ast.parse(p.read_text());shutil.copyfile(p,dest/name)
 for k in ('8','16','32','64','restore8'):
  (dest/k).mkdir(exist_ok=True)
  for p in (B/k).glob('*.py'):ast.parse(p.read_text());shutil.copyfile(p,dest/k/p.name)
 shutil.copyfile(B/'README.md',dest/'README.md');subprocess.run(['chown','-R','hong:hong',str(dest)],check=True)
 audit={'time':time.time(),'branch':'sandbox_fork_staging','implementation_unchanged':True,'binary_hashes':bins,'successes':1024,'public_remaining':0,'ready_reserves':64,'restored_workers':8,'groups':json.loads((B/'comparison.json').read_text())}
 (B/'final-audit.json').write_text(json.dumps(audit,indent=2));print('PASS: 1024/1024, all batches cleaned, unchanged implementation, 64 ready reserves, restored 8 workers')
