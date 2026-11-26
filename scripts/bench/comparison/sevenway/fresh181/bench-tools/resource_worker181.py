"""Existing CPU/IO/pressure workloads, current deployment adapters. No historical outputs."""
import os,sys,json,re,hashlib,subprocess,urllib.request,time
from pathlib import Path
from baseline_startup import setup
from pool_gate import wait
import resource_core as b
R=Path('/home/hong/codex-work/sevenway-fresh-181')
product=sys.argv[1];cfg=json.load(open(R/'tools/config.json'));cfg[product]['template']=cfg['_languages']['python']['templates'][product]
c,Sandbox=setup(product,cfg);b.pr=product
if product=='kuasar-mlink':
 from mlink_select181 import select
 select(c,[v['templates']['kuasar-mlink']for v in cfg['_languages'].values()])
def init(_):b.template=c['template']
def create():
 return Sandbox.create(c['template'],timeout=600,**c.get('create_kwargs',{})) if Sandbox else b.call(c['ctl']+['start',c['template'],'--insecure','--timeout','600'])
def cmd(s,v):
 if not Sandbox:return b.call(c['ctl']+['exec',s,'--insecure','--user','root','--','/bin/bash','-l','-c',v])
 z=s.commands.run(v,user='root',cwd='/',timeout=120);assert z.exit_code==0,z.stderr
 return z.stdout.strip()
def stream_cmd(s,command,on_stdout=None):
 import selectors,tempfile
 args=c['ctl']+['exec',s,'--insecure','--user','root','--','/bin/bash','-l','-c',command]
 with tempfile.TemporaryFile() as err:
  proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=err);sel=selectors.DefaultSelector();sel.register(proc.stdout,selectors.EVENT_READ);chunks=[];deadline=time.monotonic()+120
  try:
   while True:
    remaining=deadline-time.monotonic()
    if remaining<=0 or not sel.select(remaining):raise TimeoutError('CLI stdout deadline')
    v=os.read(proc.stdout.fileno(),65536)
    if not v:break
    text=v.decode();chunks.append(text)
    if on_stdout:on_stdout(text)
   rc=proc.wait(timeout=max(.001,deadline-time.monotonic()));err.seek(0);assert rc==0,err.read().decode()
   return ''.join(chunks).strip()
  finally:
   sel.close()
   if proc.poll() is None:proc.kill();proc.wait()
   proc.stdout.close()
def pause(s):
 if not Sandbox:return b.call(c['ctl']+['pause',s,'--memory','true'])
 if product in ('fork2','kuasar-fork'):
  req=urllib.request.Request(c['api_url']+'/sandboxes/'+s.sandbox_id+'/pause',data=b'{"memory":true}',headers={'X-API-Key':Path(c['key_file']).read_text().strip(),'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=240) as f:f.read()
 else:s.beta_pause()
def resume(s):
 if not Sandbox:b.call(c['ctl']+['resume',s,'--timeout','600']);return s
 return Sandbox.connect(s.sandbox_id,timeout=600,**{k:v for k,v in c.get('create_kwargs',{}).items() if k not in ('metadata','envs','secure','network')})
patterns={'fork2':r'/fork2-', 'kuasar-fork':r'/(?:bench108-fork|sevenway181-old-(?:store|cache))\.', 'kuasar-off':r'/bench108-off-|/kuasar-demo-(?!uffd)|/sevenway181-off-conductor\.', 'kuasar-uffd':r'/bench108-uffd-|/kuasar-demo-uffd|/sevenway181-uffd-conductor\.', 'agentenv':r'/bench108-agentenv\.|/bench108-agent-dev-acl\.', 'kuasar-mlink':r'/bench108-mlink\.', 'cube':r'/cube-sandbox-|/bench108-cube-docker\.'}
if product=='cube':
 # Cubelet explicitly moves VMM processes out of its systemd service cgroup.
 # Include only this deployment's private Docker containers, not host Docker.
 docker=['docker','-H','unix:///run/bench108-cube-docker/docker.sock']
 ids=subprocess.check_output(docker+['ps','-q','--no-trunc'],text=True).split()
 assert ids and all(re.fullmatch('[0-9a-f]{64}',v)for v in ids)
 patterns['cube']+='|/cube_sandbox/|/system.slice/docker-(?:'+'|'.join(ids)+r')\.scope'
def resources():
 detail={}
 for p in Path('/proc').glob('[0-9]*'):
  try:
   if not re.search(patterns[product],(p/'cgroup').read_text()):continue
   detail[p.name]=[(p/'comm').read_text().strip(),int(re.search(r'^Pss:\s+(\d+)',(p/'smaps_rollup').read_text(),re.M)[1]),len(list((p/'fd').iterdir()))]
  except (OSError,AttributeError):pass
 return dict(pss_mib=sum(v[1] for v in detail.values())/1024,fds=sum(v[2] for v in detail.values()),processes=detail,scope_regex=patterns[product])
paths={'fork2':['/srv/fork2/data'],'kuasar-fork':['/opt/bench108/data/fork','/opt/bench108/control/fork-sqlite'],'kuasar-off':['/opt/bench108/data/off'],'kuasar-uffd':['/opt/bench108/data/uffd'],'kuasar-mlink':['/opt/bench108/data/mlink'],'agentenv':['/opt/bench108/data/agentenv'],'cube':['/opt/bench108/data/cube','/opt/bench108/data/cube-docker-isolated181']}
b.setup=init;b.create=create;b.cmd=cmd;b.pause=pause;b.resume=resume;b.resources=resources
b.kill=lambda s:s.kill() if Sandbox else b.call(c['ctl']+['delete',s])
def allocated_disk():
 # Retry the entire read-only scan on a concurrent unlink; never use partial totals.
 for attempt in range(5):
  z=subprocess.run(['du','-sx','-B1',*paths[product]],capture_output=True,text=True)
  if z.returncode==0:return sum(int(x.split()[0]) for x in z.stdout.splitlines())
  if 'No such file or directory' not in z.stderr or attempt==4:raise RuntimeError(z.stderr[-1000:])
  time.sleep(.1)
b.disk=allocated_disk
b.ctl=c.get('ctl')
b.cpu_digest=hashlib.sha256(hashlib.shake_256(b'perf-cpu-v1').digest(1048576)*256).hexdigest()
h=hashlib.sha256()
for i in range(32):h.update(hashlib.shake_256(('fiveway'+str(i)).encode()).digest(1048576))
b.io_digest=h.hexdigest();b.press_digest=hashlib.sha256(b'paired-pressure-v1'*65536).hexdigest()
if __name__=='__main__':
 if product=='cube' and not (R/'preparation/cube-capacity/configured.json').exists():
  subprocess.run([sys.executable,str(R/'tools/cube_capacity181.py'),'cube'],check=True)
 out=R/'measurements/resources'/product;out.mkdir(parents=True,exist_ok=True)
 for i in range(51):
  b.rnd=str(i);b.path=out/f'{i:02d}.json'
  if b.path.exists():
   old=json.load(open(b.path))
   if old.get('success') and not old.get('owned_remaining'):continue
   raise RuntimeError('Review failed sample before resuming: '+str(b.path))
  wait(c)
  assert b.worker(),str(b.path)
  d=json.load(open(b.path));d.update(warmup=i==0,image_digest=cfg['_languages']['python']['digest'],filesystem_write_backing='persistent');b.save(b.path,d)
  print(product,i,'OK',flush=True)
