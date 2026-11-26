import sys,json,os,time,re,hashlib,shlex,uuid,urllib.request,subprocess
from pathlib import Path
os.environ.update(NO_PROXY='*',no_proxy='*')
sys.path.insert(0,'/home/hong/src/research/sixway-full-20261119/tools')
import runner as b
from e2b import Sandbox
R=Path('/home/hong/codex-work/sevenway-fresh-181/fork2')
c=json.loads(Path('/srv/fork2/console.json').read_text());im=json.loads(Path('/srv/fork2/data/registry/python.json').read_text())
opts=dict(api_key=c['key'],api_url=c['api'],sandbox_url='http://127.0.0.1:19611')
def setup(pr):b.template=im['template_id']
def cmd(s,command):
 r=s.commands.run(command,user='root',cwd='/',timeout=120)
 assert r.exit_code==0,r.stderr
 return r.stdout.strip()
def pause(s):
 req=urllib.request.Request(c['api']+'/sandboxes/'+s.sandbox_id+'/pause',data=b'{"memory":true}',headers={'X-API-Key':c['key'],'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=240) as r:r.read()
def resources():
 detail={}
 for p in Path('/proc').glob('[0-9]*'):
  try:
   cg=(p/'cgroup').read_text()
   if not re.search(r'/fork2-(?:runner@|shared-controller\.|conductor\.|proxy\.|switch\.|store\.)',cg):continue
   detail[p.name]=[(p/'comm').read_text().strip(),int(re.search(r'^Pss:\s+(\d+)',(p/'smaps_rollup').read_text(),re.M)[1]),len(list((p/'fd').iterdir()))]
  except (OSError,AttributeError):pass
 return dict(pss_mib=sum(r[1] for r in detail.values())/1024,fds=sum(r[2] for r in detail.values()),processes=detail)
def ready(s):
 marker='READY_'+uuid.uuid4().hex;chunks=[];seen=[]
 def got(x):
  chunks.append(x)
  if marker+'\n' in ''.join(chunks) and not seen:seen.append(time.monotonic())
 r=s.commands.run(shlex.join(['exec','/usr/local/bin/python3','-c','import sys; print(sys.argv[1], flush=True)',marker]),user='root',cwd='/',timeout=60,on_stdout=got)
 assert r.exit_code==0 and seen
 return seen[0],marker
b.pr='fork2';b.setup=setup;b.create=lambda:Sandbox.create(im['template_id'],timeout=600,**opts)
b.sid=lambda s:s.sandbox_id;b.cmd=cmd;b.kill=lambda s:s.kill();b.pause=pause;b.resume=lambda s:Sandbox.connect(s.sandbox_id,timeout=600,**opts)
b.resources=resources;b.python_ready=ready;b.disk=lambda:int(subprocess.check_output(['du','-sx','-B1','/srv/fork2/data'],text=True).split()[0])
b.cpu_digest=hashlib.sha256(hashlib.shake_256(b'perf-cpu-v1').digest(1048576)*256).hexdigest()
h=hashlib.sha256()
for i in range(32):h.update(hashlib.shake_256(('fiveway'+str(i)).encode()).digest(1048576))
b.io_digest=h.hexdigest();b.press_digest=hashlib.sha256(b'paired-pressure-v1'*65536).hexdigest()
if __name__=='__main__':
 out=R/'results/full-resources';out.mkdir(exist_ok=True)
 failures=0
 for i in range(51):
  b.rnd=str(i);b.path=out/f'{i}.json'
  success=b.worker();failures+=not success
  print(json.dumps({'round':i,'success':success}),flush=True)
 sys.exit(bool(failures))
