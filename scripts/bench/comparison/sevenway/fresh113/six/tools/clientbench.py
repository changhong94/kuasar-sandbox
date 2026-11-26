"""Real Python startup benchmark: ten samples/product, request->client print receipt."""
import argparse,json,os,subprocess,sys,time,statistics,uuid,socket,shlex,concurrent.futures as cf,fcntl,select,tempfile
from pathlib import Path
ROOT=Path('/home/hong/src/research/sixway-formal-python-113')
def save(p,o):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(o,indent=2));q.replace(p)
def setup(name,config):
 c=config[name];os.environ.update(NO_PROXY='*',no_proxy='*')
 if c['kind']=='e2b':
  os.environ.update(E2B_API_KEY=Path(c['key_file']).read_text().strip(),E2B_API_URL=c['api_url'])
  if c.get('sandbox_url'):os.environ['E2B_SANDBOX_URL']=c['sandbox_url']
  if c.get('domain'):
   os.environ['E2B_DOMAIN']=c['domain'];domain=c['domain'].split(':')[0];original=socket.getaddrinfo
   def resolve(h,*a,**kw):
    if isinstance(h,str) and h.endswith('.'+domain):h=c.get('proxy_address','127.0.0.1') if h!='api.'+domain else '127.0.0.1'
    return original(h,*a,**kw)
   socket.getaddrinfo=resolve
  if c.get('ca_file'):os.environ.update(SSL_CERT_FILE=c['ca_file'],REQUESTS_CA_BUNDLE=c['ca_file'])
  from e2b import Sandbox
 return c, Sandbox if c["kind"]=="e2b" else None
def sample(name,config,out,c,Sandbox):
 def call(args):return subprocess.check_output(args,text=True,stderr=subprocess.PIPE,timeout=90).strip()
 marker='READY_'+uuid.uuid4().hex
 python_code='import sys; print(sys.argv[1], flush=True)'
 command=shlex.join(['exec','/usr/local/bin/python3','-c',python_code,marker])
 received_ns=None
 stdout_chunks=[]
 def received(chunk):
  nonlocal received_ns
  stdout_chunks.append(chunk)
  if received_ns is None and marker+'\n' in ''.join(stdout_chunks):
   received_ns=time.perf_counter_ns()
 def stream_call(args):
  with tempfile.TemporaryFile() as errors:
   with subprocess.Popen(args,stdout=subprocess.PIPE,stderr=errors) as proc:
    output=bytearray();deadline=time.monotonic()+90
    try:
     while True:
      remaining=deadline-time.monotonic()
      if remaining<=0 or not select.select([proc.stdout],[],[],remaining)[0]:
       raise TimeoutError('exec output deadline exceeded')
      chunk=os.read(proc.stdout.fileno(),65536)
      if not chunk:break
      output.extend(chunk);received(chunk.decode('utf-8'))
     status=proc.wait(timeout=max(.001,deadline-time.monotonic()))
     errors.seek(0)
     if status:raise RuntimeError((status,errors.read().decode()))
     return output.decode().strip()
    except BaseException:
     proc.kill();proc.wait();raise
 s=None;row=dict(product=name,marker=marker,success=False,metric='create request through client stdout receipt of random Python print marker; includes interpreter startup',image_digest=config['_image_digest'],command=command,python_code=python_code,guest_argv=['/bin/bash','-l','-c',command],guest_user='root',timer_start='before client create call, includes SDK/CLI overhead',timer_end='client receives full marker plus newline on stdout')
 start=time.perf_counter_ns()
 try:
  if c['kind']=='e2b':s=Sandbox.create(c['template'],timeout=300,**c.get('create_kwargs',{}));sid=s.sandbox_id
  else:s=call(c['ctl']+['start',c['template'],'--insecure','--timeout','300']);sid=s
  row.update(sandbox_id=sid,api_ms=(time.perf_counter_ns()-start)/1e6);save(out.with_suffix('.ledger'),dict(product=name,sandbox_id=sid))
  attempts=0
  while True:
   attempts+=1
   received_ns=None;stdout_chunks.clear()
   try:
    if c['kind']=='e2b':
     r=s.commands.run(command,user='root',timeout=60,on_stdout=received);assert r.exit_code==0;r=r.stdout.strip()
    else:r=stream_call(c['ctl']+['exec',s,'--insecure','--user','root','--','/bin/bash','-l','-c',command])
    assert r==marker and received_ns is not None,(r,marker,received_ns)
    break
   except Exception:
    if attempts>=1:raise
    time.sleep(.1)
  row.update(start_ns=start,received_ns=received_ns,ready_ms=(received_ns-start)/1e6,completion_ms=(time.perf_counter_ns()-start)/1e6,received_marker=''.join(stdout_chunks).strip(),attempts=attempts,success=True)
 except Exception as e:row['error']=repr(e)
 finally:
  if s is not None:
   try:
    if c['kind']=='e2b':s.kill()
    else:call(c['ctl']+['delete',s])
    row['destroyed']=True;out.with_suffix('.ledger').unlink(missing_ok=True)
   except Exception as e:row.update(destroyed=False,cleanup_error=repr(e))
  save(out,row)
 return row['success'] and row.get('destroyed',False)
def main():
 p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('--worker');p.add_argument('--out',type=Path,required=True);a=p.parse_args();cfg=json.loads(a.config.read_text())
 if a.worker:
  t=time.monotonic();c,Sandbox=setup(a.worker,cfg)
  print(json.dumps({'ready':True,'client_preparation_ms':(time.monotonic()-t)*1000}),flush=True)
  with cf.ThreadPoolExecutor(2) as pool:
   for line in sys.stdin:
    ids=json.loads(line)
    if ids is None:break
    def run(i):
     out=a.out/f'{i+1:02d}-{a.worker}.json';ok=sample(a.worker,cfg,out,c,Sandbox);return dict(ok=ok,row=json.loads(out.read_text()))
    print(json.dumps(list(pool.map(run,ids))),flush=True)
  return 0
 names=[n for n in cfg if not n.startswith('_')];assert len(names)==6
 shared=open("/run/skyrl-threeway-benchmark.lock","a");fcntl.flock(shared,fcntl.LOCK_EX|fcntl.LOCK_NB)
 lock=(ROOT/'results/startup.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 a.out.mkdir(parents=True,exist_ok=False);save(a.out/'config-public.json',cfg)
 processes={};logs=[];samples={n:[] for n in names}
 try:
  preparation={}
  for n in names:
   log=(a.out/(n+'-client.log')).open('w');logs.append(log)
   proc=subprocess.Popen(['nsenter','--net=/run/netns/'+cfg[n]['netns'],sys.executable,str(Path(__file__).resolve()),str(a.config),'--worker',n,'--out',str(a.out)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,bufsize=1);processes[n]=proc
   preparation[n]=json.loads(proc.stdout.readline());assert preparation[n]['ready']
  save(a.out/'client-preparation.json',preparation)
  for r in range(5):
   for n in names[r%len(names):]+names[:r%len(names)]:
    save(a.out/f'round{r+1}-{n}-host.json',dict(time_ns=time.time_ns(),loadavg=Path('/proc/loadavg').read_text(),meminfo=Path('/proc/meminfo').read_text(),stat=Path('/proc/stat').read_text()))
    proc=processes[n];proc.stdin.write(json.dumps([2*r,2*r+1])+'\n');proc.stdin.flush();rows=json.loads(proc.stdout.readline());assert all(v['ok'] for v in rows),rows
    samples[n].extend(v['row']['ready_ms'] for v in rows);print('completed',n,len(samples[n]),flush=True);time.sleep(2)
  save(a.out/'summary.json',{n:dict(n=len(v),median_ms=statistics.median(v),min_ms=min(v),max_ms=max(v),concurrency=2) for n,v in samples.items()})
 finally:
  for proc in processes.values():
   if proc.poll() is None:
    proc.stdin.write('null\n');proc.stdin.flush();proc.wait(timeout=90)
  for log in logs:log.close()
 return 0
if __name__=='__main__':sys.exit(main())
