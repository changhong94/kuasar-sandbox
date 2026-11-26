import os
import pathlib,subprocess,json,sqlite3,time,hashlib,fcntl,os
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2');T=R/'tools';D=R/'results';D.mkdir(exist_ok=True)
P='/srv/fork2/bin/python-sdk'
lock=open('/run/skyrl-threeway-benchmark.lock','a');(None if os.environ.get("FORK2_FULL_LOCK_HELD")=="1" else fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB))
def run(*a):subprocess.run(a,check=True)
def status(phase): (R/'status.json').write_text(json.dumps({'phase':phase,'updated_ns':time.time_ns(),'complete':False}))
with sqlite3.connect('file:/srv/fork2/data/base/node-ctl.db?mode=ro',uri=True)as db:assert db.execute('select count(*) from sandboxes').fetchone()[0]==0
cfg=json.loads(pathlib.Path('/srv/fork2/conductor.json').read_text());pools=[x for x in cfg['units']['runner_pools']if x.get('prepared_vm')];assert len(pools)==1 and pools[0]['size']==64 and pools[0]['prepare_concurrency']==8
status('pool-preparation')
start=time.time_ns();mono=time.monotonic_ns()
run('systemctl','start','fork2-store','fork2-switch')
for _ in range(300):
 if pathlib.Path('/run/fork2/tapfd.sock').exists():break
 time.sleep(.1)
else:raise TimeoutError('fork2 switch readiness')
run('systemctl','start','fork2-conductor','fork2-proxy')
(R/'started.json').write_text(json.dumps({'start_ns':start,'start_monotonic_ns':mono,'pool':64,'prepare_concurrency':8,'binary_sha256':{x:hashlib.sha256((pathlib.Path('/srv/fork2/bin')/x).read_bytes()).hexdigest()for x in ['sandbox-ctl','node-vm-runner','node-ctl','node-checkpoint','cloud-hypervisor']}}))
status('three-language-image-startup')
p=subprocess.Popen([P,'-u',str(T/'startup.py'),'fork2'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert json.loads(p.stdout.readline())['ready']
for lang in ['python','node','ruby']:
 for i in range(51):
  p.stdin.write(json.dumps([lang,i])+'\n');p.stdin.flush();line=p.stdout.readline();assert line, p.poll();v=json.loads(line);print(v,flush=True);assert v['success']and v['destroyed']and not v.get('pool_error')
p.stdin.write('null\n');p.stdin.flush();assert p.wait(timeout=60)==0
for phase,args in [
 ('pause-restore',[P,'-u',str(T/'pause_restore.py'),'--count','50','--output',str(D/'pause-restore.json')]),
 ('resources',[P,'-u',str(T/'full_resources.py')]),
 ('storage',[P,'-u',str(T/'storage.py'),'--count','3','--output',str(D/'storage.json')]),
 ('memory',[P,'-u',str(T/'memory.py'),'fork2'])]:
 status(phase);run(*args)
status('initial-suites-finished');print('INITIAL_SUITES_COMPLETE',flush=True)
