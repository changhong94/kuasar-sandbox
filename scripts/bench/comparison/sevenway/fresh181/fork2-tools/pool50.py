import pathlib,subprocess,json,sqlite3,time,fcntl,sys,os
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2');out=R/'results/pool-preparation'/sys.argv[1];out.mkdir(parents=True,exist_ok=True)
lock=open('/run/skyrl-threeway-benchmark.lock','a');(None if os.environ.get("FORK2_FULL_LOCK_HELD")=="1" else fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB))
P='/srv/fork2/data/base/node-ctl.db'
run=lambda *a:subprocess.run(a,check=True,stdout=subprocess.DEVNULL)
def empty():
 with sqlite3.connect('file:'+P+'?mode=ro',uri=True)as db:assert db.execute('select count(*)from sandboxes').fetchone()[0]==0
cfg=json.load(open('/srv/fork2/conductor.json'));pp=[p for p in cfg['units']['runner_pools']if p.get('prepared_vm')];assert len(pp)==1 and pp[0]['size']==64 and pp[0]['prepare_concurrency']==8
run('systemctl','start','fork2-store','fork2-switch')
for i in range((int(sys.argv[2]) if len(sys.argv)>2 else 50)+1):
 existing=out/f'{i:02d}.json'
 if existing.exists():
  assert json.load(open(existing)).get('success');continue
 empty();run('systemctl','stop','fork2-conductor','fork2-proxy')
 units=[x.split()[0]for x in subprocess.check_output(['systemctl','list-units','fork2-runner@*','--plain','--no-legend'],text=True).splitlines()if x.startswith('fork2-runner@')]
 if units:run('systemctl','stop',*units)
 run('systemctl','stop','fork2-shared')
 subprocess.run(['systemctl','reset-failed','fork2-conductor','fork2-proxy','fork2-shared'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 start=time.time_ns();mono=time.monotonic_ns();run('systemctl','start','fork2-conductor','fork2-proxy')
 for _ in range(1500):
  try:
   x=json.loads(subprocess.check_output(['curl','-sf','--max-time','2','--unix-socket','/run/fork2/node.sock','http://localhost/internal/admin/resource-pressure'],stderr=subprocess.DEVNULL))
   pool=next(p for p in x['runner_pools']if p['name']=='prepared')
   if pool['states']=={'idle':64}:break
  except (subprocess.CalledProcessError,ValueError,KeyError,StopIteration):pass
  time.sleep(.02)
 else:raise TimeoutError('pool fill')
 h=pool['preparation_history'];assert len(h)==64 and all(v['started_unix_ns']>=start for v in h)
 rec=dict(iteration=i,warmup=i==0,start_ns=start,request_to_full_ms=(time.monotonic_ns()-mono)/1e6,slots=h,slot_span_ms=(max(v['ready_unix_ns']for v in h)-min(v['started_unix_ns']for v in h))/1e6,success=True)
 (out/f'{i:02d}.json').write_text(json.dumps(rec,indent=2));print(json.dumps({k:v for k,v in rec.items()if k!='slots'}),flush=True)
print('COMPLETE',flush=True)
