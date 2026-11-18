from pathlib import Path
import fcntl,json,os,re,sqlite3,subprocess as sp,time,shutil
B=Path('/home/hong/src/research/report-revision-113');cfg=json.loads((B/'tools/config.json').read_text())
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 # Native reference location resolution is owned by these idle test conductors.
 for product,afile,unit in [('kuasar-off','/home/hong/deploy/comparison/kuasar-state/access.json','kuasar-comparison-node'),('kuasar-uffd','/home/hong/deploy/private-pilot/uffd-state/access.json','bench-private-uffd-serve')]:
  work=Path(json.loads(Path(afile).read_text())['work_dir'])
  with sqlite3.connect((work/'lib/node-ctl.db').as_uri()+'?mode=ro',uri=True) as db:assert db.execute('SELECT COUNT(*) FROM sandboxes').fetchone()[0]==0
  path=work/'conductor.yaml';text=path.read_text();backup=B/'private'/(product+'-conductor-original.yaml')
  if not backup.exists():backup.write_text(text);backup.chmod(0o600)
  old='file:///home/hong/src/research/startup-modes-113/native';new=(B/'native').as_uri()
  assert old in text or new in text
  path.write_text(text.replace(old,new))
  with path.open('rb') as f:os.fsync(f.fileno())
  sp.run(['systemctl','reload',unit],check=True)
 # Reload only the drained, owned fork service to activate the SDK metadata selector.
 start=time.monotonic_ns()
 sp.run(['nsenter','--net=/run/netns/py113-fork','python3',str(B/'reset-owned-fork.py')],check=True)
 code="import sys,json;sys.path.insert(0,"+repr(str(B/'tools'))+");from pool_gate import wait;c=json.load(open("+repr(str(B/'tools/config.json'))+"));print(json.dumps(wait(c['kuasar-fork'],capacity=64,timeout=600)))"
 fork=json.loads(sp.check_output(['nsenter','--net=/run/netns/py113-fork','python3','-c',code],text=True))
 fork_ms=(time.monotonic_ns()-start)/1e6
 c=cfg['kuasar-mlink'];ctl=['nsenter','--net=/run/netns/'+c['netns']]+c['ctl']
 assert json.loads(sp.check_output(ctl+['list','--json'],text=True))==[]
 path=Path('/home/hong/deploy/mlink-generic/start.sh');text=path.read_text()
 backup=B/'private/mlink-start-original.sh'
 if not backup.exists():backup.write_text(text)
 assert 'write_node_configs 2 1000 2 2 2' in text or 'write_node_configs 64 1000 2 2 64' in text
 path.write_text(text.replace('write_node_configs 2 1000 2 2 2','write_node_configs 64 1000 2 2 64'))
 path=Path('/home/hong/deploy/mlink-generic/mlink-env.sh');text=path.read_text()
 backup=B/'private/mlink-env-original.sh'
 if not backup.exists():backup.write_text(text)
 path.write_text(text.replace('POOL_CAPACITY=2','POOL_CAPACITY=64'))
 start=time.monotonic_ns();sp.run(['systemctl','restart','bench-mlink-generic'],check=True)
 sp.run(['python3',str(B/'tools/switch-language.py'),str(B/'tools/config.json'),'python',str(B/'results/preparation/python')],check=True)
 code=code.replace("c['kuasar-fork']","c['kuasar-mlink']")
 mlink=json.loads(sp.check_output(['nsenter','--net=/run/netns/'+c['netns'],'python3','-c',code],text=True))
 (B/'formal-preparation.json').write_text(json.dumps({'capacity':64,'fork':fork,'mlink':mlink,'fork_service_to_pool_ready_ms':fork_ms,'mlink_service_to_pool_ready_ms':(time.monotonic_ns()-start)/1e6},indent=2))
 shutil.copyfile('/home/hong/src/research/startup-modes-113/progress',B/'progress');(B/'progress').chmod(0o755)
 print('FORMAL PROFILE READY: 113, both pools 64, no active assigned sandboxes')
