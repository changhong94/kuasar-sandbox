import sys,os,json,shlex,socket,time,uuid,hashlib,subprocess as sp,statistics as st,threading,concurrent.futures as cf,re,fcntl,traceback
from pathlib import Path
D=Path('/home/hong/deploy/comparison');P=Path('/home/hong/deploy/private-pilot');prods=['kuasar-off','cube','agentenv','kuasar-uffd','kuasar-mlink','kuasar-fork']
ns=dict(zip(prods,['bench113','bench113','bench113','bench113-u','bench113-m-generic','py113-fork']))
clock=time.monotonic
def save(p,obj):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(obj,indent=2));t.replace(p)
def call(args,timeout=120):
 z=sp.run(list(map(str,args)),capture_output=True,text=True,timeout=timeout)
 if z.returncode:raise RuntimeError(z.stderr[-900:] or z.stdout[-900:])
 return z.stdout.strip()
def setup(pr):
 global c,kw,template,ctl
 sys.path.insert(0, '/home/hong/src/research/sevenway-current-20261126/six/tools')
 import clientbench
 cfg=json.loads(Path('/home/hong/src/research/sevenway-current-20261126/six/tools/config.json').read_text())
 c,_=clientbench.setup(pr,cfg);kw=c.get('create_kwargs',{});template=c['template']
 if pr=='kuasar-mlink':ctl=c['ctl']
def create():
 if pr=='kuasar-mlink':return call(ctl+['start',template,'--insecure','--timeout','300'])
 from e2b import Sandbox
 return Sandbox.create(template,timeout=300,**kw)
def sid(s):return s if isinstance(s,str) else s.sandbox_id
def cmd(s,v):
 if pr=='kuasar-mlink':return call(ctl+['exec',s,'--insecure','--','/bin/bash','-l','-c',v])
 z=s.commands.run(v,user='root',timeout=60);assert z.exit_code==0;return z.stdout.strip()
def ready(s,v,expected):
 for i in range(40):
  try:
   assert cmd(s,v)==expected;return
  except Exception:
   if i==39:raise
   time.sleep(.1)
def kill(s):
 if pr=='kuasar-mlink':call(ctl+['delete',s])
 else:s.kill()
def pause(s):
 if pr=='kuasar-mlink':call(ctl+['pause',s,'--memory','true'])
 else:s.beta_pause()
def resume(s):
 if pr=='kuasar-mlink':call(ctl+['resume',s,'--timeout','300']);return s
 from e2b import Sandbox
 return Sandbox.connect(sid(s),timeout=300)
CPU="""import hashlib,time,json
b=hashlib.shake_256(b'perf-cpu-v1').digest(1048576);h=hashlib.sha256();t=time.monotonic();c=time.process_time()
for i in range(256): h.update(b)
print(json.dumps([h.hexdigest(),(time.monotonic()-t)*1000,(time.process_time()-c)*1000]))"""
IO="""import hashlib,time,json,os
h=hashlib.sha256();t=time.monotonic()
with open('/tmp/fiveway.bin','wb') as f:
 for i in range(32):
  b=hashlib.shake_256(('fiveway'+str(i)).encode()).digest(1048576);h.update(b);f.write(b)
 f.flush();os.fsync(f.fileno())
print(json.dumps([h.hexdigest(),(time.monotonic()-t)*1000]))"""
MEM="""import mmap,time
b=mmap.mmap(-1,128*1048576);block=b'M'*1048576
for i in range(128): b[i*1048576:(i+1)*1048576]=block
time.sleep(4);b.close();time.sleep(4);print('MEM_OK')"""
PRESS="python3 -c 'import hashlib; print(hashlib.sha256(b\"paired-pressure-v1\"*65536).hexdigest())'"
def py(s,code):return cmd(s,'python3 -c '+shlex.quote(code))
def resources():
 units={'kuasar-off':'kuasar-comparison','kuasar-uffd':'bench-private-uffd','agentenv':'agentenv-comparison','cube':'cube-sandbox-','kuasar-mlink':'bench-mlink-generic','kuasar-fork':'bench-python113-fork'}
 ids=set();detail={}
 if pr=='cube':
  out=call(['docker','-H','unix:///run/cube-comparison/docker.sock','ps','-q']).split()
  if out:
   for a in call(['docker','-H','unix:///run/cube-comparison/docker.sock','inspect','--format','{{.State.Pid}}',*out]).split():ids.add(int(a))
 tab={}
 for f in Path('/proc').glob('[0-9]*'):
  try:
   pid=int(f.name);cg=(f/'cgroup').read_text();ps=(f/'stat').read_text().rsplit(')',1)[1].split();tab[pid]=(int(ps[1]),f)
   if any(u in cg for u in {'kuasar-off':['bench-revision113-cache-off.service'],'kuasar-uffd':['bench-revision113-cache-uffd.service'],'kuasar-fork':['bench-revision113-cache.service','bench-revision113-store.service']}.get(pr,[])) or units[pr] in cg or (pr=='kuasar-off' and 'bench-kuasar-off-' in cg) or (pr=='kuasar-off' and 'kuasar-demo-' in cg and 'uffd113abc' not in cg) or (pr=='kuasar-uffd' and 'kuasar-demo-uffd113abc' in cg) or (pr=='cube' and '/cube_sandbox/' in cg):ids.add(pid)
  except (OSError,ValueError):pass
 while True:
  new={i for i,(parent,f) in tab.items() if parent in ids}-ids
  if not new:break
  ids.update(new)
 for i in ids:
  try:
   f=tab[i][1];pss=int(re.search(r'^Pss:\s+(\d+)',(f/'smaps_rollup').read_text(),re.M)[1]);detail[str(i)]=[(f/'comm').read_text().strip(),pss,len(list((f/'fd').iterdir()))]
  except (OSError,KeyError,TypeError):pass
 return dict(pss_mib=sum(x[1] for x in detail.values())/1024,fds=sum(x[2] for x in detail.values()),processes=detail)
def disk():
 paths={'kuasar-off':['comparison/cube-xfs/kuasar'],'cube':['comparison/cube-xfs/data','comparison/cube-xfs/support'],'agentenv':['comparison/agentenv'],'kuasar-uffd':['uffd'],'kuasar-mlink':['mlink-generic'],'kuasar-fork':['/home/hong/src/research/python-latest-113/data/fork','/home/hong/src/research/python-latest-113/control/fork-sqlite']}[pr]
 return sum(int(v.split()[0]) for v in call(['du','-sx','-B1',*[Path('/home/hong/data')/p for p in paths]]).splitlines())
def python_ready(s):
 # Record receipt, not command exit. A fresh interpreter is launched per call.
 marker='READY_'+uuid.uuid4().hex
 command=shlex.join(['exec','/usr/local/bin/python3','-c','import sys; print(sys.argv[1], flush=True)',marker])
 chunks=[];received=None
 def output(v):
  nonlocal received
  chunks.append(v)
  if received is None and marker+'\n' in ''.join(chunks):received=clock()
 if pr=='kuasar-mlink':
  import select,tempfile
  with tempfile.TemporaryFile() as error:
   with sp.Popen(ctl+['exec',s,'--insecure','--user','root','--','/bin/bash','-l','-c',command],stdout=sp.PIPE,stderr=error) as process:
    deadline=clock()+90
    try:
     while True:
      left=deadline-clock()
      if left<=0 or not select.select([process.stdout],[],[],left)[0]:raise TimeoutError('print deadline')
      chunk=os.read(process.stdout.fileno(),65536)
      if not chunk:break
      output(chunk.decode())
     assert process.wait(timeout=10)==0
    except BaseException:process.kill();process.wait();raise
 else:
  r=s.commands.run(command,user='root',timeout=60,on_stdout=output);assert r.exit_code==0
 assert ''.join(chunks).strip()==marker and received is not None
 return received,marker

def worker():
 setup(pr);owned={};lock=threading.Lock();out={'product':pr,'round':rnd,'warmup':str(rnd)=='0','template':template,'stages':{},'pressure':[]};stages=out['stages']
 def own(s):
  with lock:owned[sid(s)]=s;save(path.with_suffix('.ledger'),list(owned))
  return s
 def drop(s):
  kill(s)
  with lock:owned.pop(sid(s));save(path.with_suffix('.ledger'),list(owned))
 def record(n):stages[n]=dict(**resources(),allocated_bytes=disk())
 try:
  record('before');t=clock();s=own(create());out['api_ms']=(clock()-t)*1000;received,marker=python_ready(s);out.update(ready_ms=(received-t)*1000,ready_marker=marker,ready_metric='client Python print receipt')
  out['platform']=cmd(s,'nproc; grep MemTotal /proc/meminfo; python3 --version')
  record('live');out['short_ms']=[]
  for _ in range(8):
   t=clock();cmd(s,'true');out['short_ms'].append((clock()-t)*1000)
  out['cpu']=json.loads(py(s,CPU));out['io']=json.loads(py(s,IO));assert out['cpu'][0]==cpu_digest and out['io'][0]==io_digest
  record('written')
  with cf.ThreadPoolExecutor(1) as pool:
   fut=pool.submit(py,s,MEM);out['mem_samples']=[];t=clock()
   while not fut.done():out['mem_samples'].append([clock()-t,resources()['pss_mib']]);time.sleep(.5)
   assert fut.result()=='MEM_OK'
  record('released')
  t=clock();pause(s);out['pause_ms']=(clock()-t)*1000;record('paused')
  t=clock();s=resume(s);received,marker=python_ready(s);out['resume_ms']=(received-t)*1000
  if pr=='kuasar-fork':out['filesystem_write_backing']='qcow2-ext4'
  assert cmd(s,'sha256sum /tmp/fiveway.bin').split()[0]==io_digest
  drop(s);time.sleep(2);record('settled')
  def request(i):
   s=None;z={'i':i};t=clock()
   try:
    s=own(create());received,marker=python_ready(s);z.update(ready_ms=(received-t)*1000,marker=marker);assert cmd(s,PRESS)==press_digest;z['work_ms']=(clock()-t)*1000;z['success']=True
   except Exception as e:z.update(success=False,error=str(e)[:500])
   finally:
    if s is not None:drop(s)
   return z
  t=clock()
  with cf.ThreadPoolExecutor(2) as pool:out['pressure']=list(pool.map(request,range(8)))
  out['throughput']=sum(x['success'] for x in out['pressure'])/(clock()-t)
  out['success']=True
 except Exception:out['success']=False;out['error']=traceback.format_exc()
 finally:
  for s in list(owned.values()):
   try:drop(s)
   except Exception:out['cleanup_error']=traceback.format_exc()
  out['owned_remaining']=list(owned);save(path,out)
 return out['success'] and not owned
if __name__=='__main__':
 if sys.argv[1]=='worker':
  _,_,pr,rnd,target=sys.argv;path=Path(target)
  cpu_digest=hashlib.sha256(hashlib.shake_256(b'perf-cpu-v1').digest(1048576)*256).hexdigest()
  h=hashlib.sha256()
  for i in range(32):h.update(hashlib.shake_256(('fiveway'+str(i)).encode()).digest(1048576))
  io_digest=h.hexdigest();press_digest=hashlib.sha256(b'paired-pressure-v1'*65536).hexdigest()
  sys.exit(0 if worker() else 1)
 root=Path(sys.argv[2]);root.mkdir(exist_ok=False);script=root/'runner.py';script.write_bytes(Path(__file__).read_bytes())
 assert os.environ.get('FIVEWAY_LOCK_HELD') == '1'
 for r in range(51):
  for pr in prods[r%len(prods):]+prods[:r%len(prods)]:
   n=f'{r}-{pr}';print('START',n,flush=True)
   if int(re.search(r'MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text())[1])<16*1024**2:raise RuntimeError('host memory guard')
   with (root/(n+'.log')).open('w') as log:
    rc=sp.run(['nsenter','--net=/run/netns/'+ns[pr],sys.executable,str(script),'worker',pr,str(r),str(root/(n+'.json'))],stdout=log,stderr=log).returncode
   if rc:raise RuntimeError('failed '+n)
   print('END',n,flush=True)
 save(root/'complete.json',{'runs':306,'formal_per_product':50,'warmup_per_product':1})
