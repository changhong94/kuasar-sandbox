import os
import pathlib,subprocess,json,sqlite3,time,hashlib,fcntl,os
R=pathlib.Path('/home/hong/src/research/sevenway-current-20261126/fork2');T=R/'tools';D=R/'results';D.mkdir(exist_ok=True)
P='/srv/fork2/bin/python-sdk'
lock=open('/run/skyrl-threeway-benchmark.lock','a');(None if os.environ.get("FORK2_FULL_LOCK_HELD")=="1" else fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB))
def run(*a):subprocess.run(a,check=True)
def status(phase): (R/'status.json').write_text(json.dumps({'phase':phase,'updated_ns':time.time_ns(),'complete':False}))
with sqlite3.connect('file:/home/hong/src/research/fork2-control-persistent/node-ctl.db?mode=ro',uri=True)as db:assert db.execute('select count(*) from sandboxes').fetchone()[0]==0
cfg=json.loads(pathlib.Path('/srv/fork2/conductor.json').read_text());pools=[x for x in cfg['units']['runner_pools']if x.get('prepared_vm')];assert len(pools)==1 and pools[0]['size']==64 and pools[0]['prepare_concurrency']==8
status('pool-preparation')
start=time.time_ns();mono=time.monotonic_ns()
run('systemctl','start','fork2-store','fork2-switch')
for _ in range(300):
 if pathlib.Path('/run/fork2/tapfd.sock').exists():break
 time.sleep(.1)
else:raise TimeoutError('fork2 switch readiness')
run('systemctl','start','fork2-conductor','fork2-proxy')
(R/'burst0-retry-started.json').write_text(json.dumps({'start_ns':start,'start_monotonic_ns':mono,'pool':64,'prepare_concurrency':8,'binary_sha256':{x:hashlib.sha256((pathlib.Path('/srv/fork2/bin')/x).read_bytes()).hexdigest()for x in ['sandbox-ctl','node-vm-runner','node-ctl','node-checkpoint','cloud-hypervisor']}}))
target=D/'paced/0'
if target.exists():target.rename(target.with_name('0-incomplete-'+str(time.time_ns())))
(None if os.environ.get("FORK2_FULL_LOCK_HELD")=="1" else fcntl.flock(lock,fcntl.LOCK_UN))
status('256-requests-0-final-validation')
run(P,'-u',str(T/'burst_latest.py'),str(target),'0')
with sqlite3.connect('file:/home/hong/src/research/fork2-control-persistent/node-ctl.db?mode=ro',uri=True)as d:assert d.execute('select count(*) from sandboxes').fetchone()[0]==0
run('systemctl','stop','fork2-conductor','fork2-proxy')
units=[x.split()[0]for x in subprocess.check_output(['systemctl','list-units','fork2-runner@*','--plain','--no-legend'],text=True).splitlines()if x.startswith('fork2-runner@')]
if units:run('systemctl','stop',*units)
run('systemctl','stop','fork2-shared-controller','fork2-store','fork2-switch')
remaining=subprocess.check_output(['systemctl','list-units','fork2-*','--state=running','--plain','--no-legend'],text=True)
active=[s for s in remaining.splitlines()if 'fork2-sevenway-'not in s];assert not active,active
(R/'cleanup.json').write_text(json.dumps({'sandboxes_remaining':0,'runtime_services_running':active,'other_known_process_alive':pathlib.Path('/proc/957181').exists(),'finished_ns':time.time_ns()},indent=2))
(R/'status.json').write_text(json.dumps({'phase':'tests-finished-report-pending','complete':False,'finished_ns':time.time_ns()}))
print('ALL_TEST_SUITES_COMPLETE',flush=True)
