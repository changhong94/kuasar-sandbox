from pathlib import Path
import fcntl,json,subprocess,hashlib,shutil,ast,time
B=Path('/home/hong/src/research/network-reset-113');F=Path('/home/hong/src/research/python-latest-113');Q=F/'src/kuasar-fork/kuasar-io/kuasar';CH=F/'src/kuasar-fork/cloud-hypervisor/cloud-hypervisor';bench=Path('/home/hong/src/research/report-revision-113/bench')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for repo in (Q,CH,bench):
  assert subprocess.check_output(['runuser','-u','hong','--','git','-C',str(repo),'branch','--show-current'],text=True).strip()=='sandbox_fork_staging'
  subprocess.run(['runuser','-u','hong','--','git','-C',str(repo),'diff','--check'],check=True)
 state=json.loads((F/'data/fork/adapter-state.json').read_text());assert len(state)==64 and all(x['pool_state']=='ready' and x['network_state']=='ready' for x in state.values())
 hashes={p:digest(Q/'integrations/e2b'/p) for p in ('template_pool.py','vm_backend.py','image_pool.py','server.py')}
 groups={}
 for k in ('8','4','8-repeat'):
  d=json.loads((B/k/'deployment.json').read_text());assert hashes==d['source_hashes']
  r=json.loads((B/k/'results/burst256/kuasar-fork/result.json').read_text());assert r['batch_valid'] and r['print']['completed']==256 and r['failed_requests']==0 and not r['public_remaining'] and r['all_private_files_verified'] and r['survivors_verified_after_half_destroyed'] and r['cleanup_quiescence_verified']
  assert r['pool_while_instances_retained']['assigned']==256 and r['pool_while_instances_retained']['ready']==64
  groups[k]=json.loads((B/k/'summary.json').read_text())
 proof=json.loads((B/'disk-backing-verification.json').read_text());assert len(proof['rows'])==2 and all(r['success'] for r in proof['rows']) and not proof['owned'] and not proof['pending']
 live=json.loads((B/'live-fork-validation/rows.json').read_text());assert live and all(r['success'] and r['independent_files'] and r['independent_destroy'] for r in live)
 bins={}
 for deployed,built in ((F/'deploy/fork/bin/cloud-hypervisor',Path('/home/hong/src/research/sixway-integrated-20261118/ch-target/release/cloud-hypervisor')),(F/'deploy/fork/bin/sandboxer',Path('/home/hong/src/research/fork-features-113/target/release/cloud_hypervisor'))):
  assert digest(deployed)==digest(built);bins[deployed.name]=digest(deployed)
 assert 'E2B_TEMPLATE_POOL_WORKERS=8' in Path('/etc/systemd/system/bench-python113-fork.service.d/zzzz-parallel-refill.conf').read_text()
 dest=bench/'scripts/bench/comparison/sixway/network-reset';dest.mkdir(parents=True,exist_ok=True)
 for name in ('run-final.py','verify_disk_network.py','finalize.py','report.py','plot_helpers.py'):
  p=B/name;ast.parse(p.read_text());shutil.copyfile(p,dest/name)
 for k in groups:
  (dest/k).mkdir(exist_ok=True)
  for p in (B/k).glob('*.py'):ast.parse(p.read_text());shutil.copyfile(p,dest/k/p.name)
 shutil.copyfile(B/'README.md',dest/'README.md');subprocess.run(['chown','-R','hong:hong',str(dest)],check=True)
 audit=dict(time=time.time(),branch='sandbox_fork_staging',source_hashes=hashes,binary_hashes=bins,user_instances_remaining=0,ready=64,default_workers=8,groups=groups,network_disk_proof=proof)
 (B/'final-audit.json').write_text(json.dumps(audit,indent=2));print('PASS: 768/768, cleaned, 64 reserves, default 8, staging only; matching deployed binaries')
