import os
import pathlib,json,time,sqlite3,subprocess,uuid,fcntl
from e2b import Sandbox
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2');D=R/'results';P=R/'results/lifecycle.json';c=json.load(open('/srv/fork2/console.json'));reg=json.load(open('/srv/fork2/data/registry/python.json'));opts=dict(api_key=c['key'],api_url=c['api'],sandbox_url='http://127.0.0.1:19611')
lock=open('/run/skyrl-threeway-benchmark.lock','a');(None if os.environ.get("FORK2_FULL_LOCK_HELD")=="1" else fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB))
def gate():
 t=time.perf_counter_ns()
 while (time.perf_counter_ns()-t)/1e9<180:
  with sqlite3.connect('file:/srv/fork2/data/base/node-ctl.db?mode=ro',uri=True)as d:
   ids=[x[0]for x in d.execute('select run_id from prepared_vm_leases')];n=d.execute('select count(*) from sandboxes').fetchone()[0]
  if len(ids)==64 and n==0:
   raw=subprocess.check_output(['curl','--fail','--silent','--show-error','--max-time','3','--unix-socket','/run/fork2/node.sock','http://localhost/internal/admin/resource-pressure'],timeout=5)
   pools=json.loads(raw).get('runner_pools',[])
   if any(p.get('idle_target')==64 and p.get('states',{}).get('idle')==64 and p.get('states',{}).get('starting',0)==0 for p in pools):return(time.perf_counter_ns()-t)/1e6
  time.sleep(.02)
 raise TimeoutError('pool refill')
rows=[]
for i in range(51):
 gate();s=None;row={'iteration':i,'warmup':i==0,'success':False}
 try:
  s=Sandbox.create(reg['template_id'],timeout=300,**opts);row['id']=s.sandbox_id
  token=uuid.uuid4().hex;r=s.commands.run('echo '+token,user='root',cwd='/',timeout=60);assert r.exit_code==0 and r.stdout.strip()==token
  row['delete_start_ns']=time.time_ns();t=time.perf_counter_ns();s.kill();s=None;row['delete_ack_ms']=(time.perf_counter_ns()-t)/1e6
  row['refill_wait_ms']=gate();row['delete_through_refill_ms']=(time.perf_counter_ns()-t)/1e6;row['success']=True
 finally:
  if s:s.kill()
  rows.append(row);P.write_text(json.dumps(rows,indent=2))
 print('lifecycle',i,row['success'],flush=True)
