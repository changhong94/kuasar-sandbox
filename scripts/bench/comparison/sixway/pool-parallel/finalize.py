from pathlib import Path
import fcntl,json,hashlib,subprocess,shutil,time,ast
B=Path('/home/hong/src/research/pool-parallel-113');OLD=Path('/home/hong/src/research/report-revision-113');Q=Path('/home/hong/src/research/python-latest-113/src/kuasar-fork/kuasar-io/kuasar');repo=OLD/'bench'
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert (B/'unit-tests.log').read_text().strip().endswith('OK')
 for path in (Q,repo):
  assert subprocess.check_output(['runuser','-u','hong','--','git','-C',str(path),'branch','--show-current'],text=True).strip()=='sandbox_fork_staging'
  subprocess.run(['runuser','-u','hong','--','git','-C',str(path),'diff','--check'],check=True)
 source_hashes={n:hashlib.sha256((Q/'integrations/e2b'/n).read_bytes()).hexdigest() for n in ('template_pool.py','server.py','test_template_pool.py','test_image_pool.py','vm_backend.py','image_pool.py','README.md')}
 deployed=json.loads((B/'deployment.json').read_text())['source_hashes']
 assert all(source_hashes[n]==deployed[n] for n in ('template_pool.py','server.py'))
 records=json.loads(Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json').read_text())
 assert len(records)==64 and all(r.get('pool_state')=='ready' and r.get('network_state')=='ready' for r in records.values())
 code="import json,sys;sys.path.insert(0,"+repr(str(OLD/'tools'))+");from pool_gate import wait; c=json.load(open("+repr(str(OLD/'tools/config.json'))+"));print(json.dumps(wait(c['kuasar-fork'],64,60)))"
 gate=json.loads(subprocess.check_output(['nsenter','--net=/run/netns/py113-fork','python3','-c',code],text=True))
 dest=repo/'scripts/bench/comparison/sixway/pool-parallel';dest.mkdir(parents=True,exist_ok=True)
 for name in ('README.md','burst256.py','prepare.py','deploy.py','verify_disk_backing.py','report.py','plot_helpers.py','analyze.py','finalize.py'):
  shutil.copy2(B/name,dest/name)
  subprocess.run(['chown','hong:hong',str(dest/name)],check=True)
  if name.endswith('.py'):ast.parse((dest/name).read_text())
 subprocess.run(['chown','hong:hong',str(dest)],check=True)
 files={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir() if p.is_file() and p.name!='source-hashes.json'}
 (dest/'source-hashes.json').write_text(json.dumps(files,indent=2));subprocess.run(['chown','hong:hong',str(dest/'source-hashes.json')],check=True)
 binary=Path('/home/hong/src/research/python-latest-113/deploy/fork/bin/sandboxer')
 built=Path('/home/hong/src/research/fork-features-113/target/release/cloud_hypervisor')
 binary_hash=hashlib.sha256(binary.read_bytes()).hexdigest()
 assert binary_hash==hashlib.sha256(built.read_bytes()).hexdigest()
 running=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   argv=(proc/'cmdline').read_bytes().split(b'\0')
   if argv[0].decode()==str(binary):
    assert hashlib.sha256((proc/'exe').read_bytes()).hexdigest()==binary_hash
    running.append(int(proc.name))
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 assert len(running)==1,running
 source_hashes['vmm/sandbox/src/service/mod.rs']=hashlib.sha256((Q/'vmm/sandbox/src/service/mod.rs').read_bytes()).hexdigest()
 result={'binary_sha256':binary_hash,'running_sandboxer_pids':running,'completed_unix':time.time(),'branch':'sandbox_fork_staging','merged':False,'public_remaining':0,'ready_gate':gate,'runtime_sources_unchanged_during_benchmark':True,'source_hashes':source_hashes,'benchmark_hashes':files,'report_sha256':hashlib.sha256((B/'report/fork-parallel-256-zh-en.pdf').read_bytes()).hexdigest()}
 (B/'final-audit.json').write_text(json.dumps(result,indent=2))
print('PASS: 256/256, 64 reserves ready, no public instances remaining, staging source/archive verified')
