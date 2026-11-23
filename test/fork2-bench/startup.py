#!/usr/bin/env python3
"""Fresh Python interpreter, request to first complete random stdout marker."""
import argparse,json,pathlib,sqlite3,subprocess,time,uuid,statistics,shlex,os
os.environ.update(NO_PROXY="*",no_proxy="*")
from e2b import Sandbox
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--count',type=int,default=10);p.add_argument('--language',choices=['python','node','ruby'],default='python');a=p.parse_args()
cfg=json.loads(pathlib.Path('/srv/fork2/console.json').read_text());im=json.loads(pathlib.Path('/srv/fork2/data/registry/'+a.language+'.json').read_text())
opts=dict(api_key=cfg['key'],api_url=cfg['api'],sandbox_url='http://127.0.0.1:19211')
def pool():
 end=time.monotonic()+60
 while time.monotonic()<end:
  with sqlite3.connect('file:/srv/fork2/data/base/node-ctl.db?mode=ro',uri=True) as db:ids=[r[0] for r in db.execute('select p.run_id from prepared_vm_leases p join run_pool_ownership o on o.run_id=p.run_id')]
  if len(ids)==2:
   logs=subprocess.check_output(['journalctl',*[v for i in ids for v in ('-u','fork2-runner@'+i+'.service')],'--since','-1 hour','--no-pager','-o','cat'],text=True)
   if all('prepared VM ready run_id='+i in logs for i in ids):return
  time.sleep(.02)
 raise TimeoutError('two prepared VM readiness acknowledgements')
rows=[]
for i in range(a.count+1):
 row=None;pool();marker='READY_'+uuid.uuid4().hex;seen=[];stdout=[];s=None
 interpreter, flag, code = {'python':('/usr/local/bin/python3','-c','import sys; print(sys.argv[1], flush=True)'), 'node':('/usr/local/bin/node','-e','console.log(process.argv[1])'), 'ruby':('/usr/local/bin/ruby','-e','STDOUT.sync=true; puts ARGV[0]')}[a.language]
 command='exec '+interpreter+' '+flag+' '+shlex.quote(code)+' '+marker
 if a.language in ('node','ruby'):
  reference=json.loads(pathlib.Path('/opt/bench108/results/five-rounds-108/round5/'+a.language+'/config-public.json').read_text())
  assert reference['_image_digest']==im['manifest']
  command='cd /; '+shlex.join(['exec','/usr/bin/env','-i',*reference['_env'],reference['_binary'],reference['_flag'],reference['_code'],marker])
 def receive(chunk):
  stdout.append(chunk)
  if marker+'\n' in ''.join(stdout) and not seen:seen.append(time.perf_counter_ns())
 start=time.perf_counter_ns()
 try:
  s=Sandbox.create(template=im['template_id'],timeout=300,**opts);ready=time.perf_counter_ns()
  r=s.commands.run(command,user='root',cwd='/',timeout=60,on_stdout=receive)
  if r.exit_code or not seen:raise RuntimeError('missing successful random print')
  row={'iteration':i,'warmup':i==0,'sandbox_id':s.sandbox_id,'create_api_ms':(ready-start)/1e6,'print_ms':(seen[0]-start)/1e6,'exec_ms':(seen[0]-ready)/1e6,'load':os.getloadavg()}
 finally:
  if s:
   t=time.perf_counter_ns();s.kill();deleted=time.perf_counter_ns()
 if row is not None:
  row['delete_ack_ms']=(deleted-t)/1e6;pool();row['refill_after_delete_ms']=(time.perf_counter_ns()-deleted)/1e6;rows.append(row);print(json.dumps(row),flush=True)
  pathlib.Path(a.output).write_text(json.dumps({'image_digest':im['manifest'],'command':command,'samples':rows},indent=2))
for key in ('create_api_ms','print_ms','exec_ms','delete_ack_ms','refill_after_delete_ms'):
 values=[r[key] for r in rows if not r['warmup']];print(key,statistics.median(values),max(values),flush=True)
