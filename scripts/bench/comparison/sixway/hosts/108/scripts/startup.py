"""Startup-only benchmark: ten samples/product; preparation excluded, request->READY included."""
import argparse,json,os,subprocess,sys,time,statistics,uuid,socket,shlex,concurrent.futures as cf,fcntl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def save(p,o):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(o,indent=2));q.replace(p)
def worker(name,config,out):
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
 def call(args):return subprocess.check_output(args,text=True,stderr=subprocess.PIPE,timeout=90).strip()
 marker='READY_'+uuid.uuid4().hex
 command='printf '+shlex.quote(marker)
 s=None;row=dict(product=name,marker=marker,success=False,metric='create request through client receipt of random shell printf marker',image_digest=config['_image_digest'])
 start=time.perf_counter_ns()
 try:
  if c['kind']=='e2b':s=Sandbox.create(c['template'],timeout=300,**c.get('create_kwargs',{}));sid=s.sandbox_id
  else:s=call(c['ctl']+['start',c['template'],'--insecure','--timeout','300']);sid=s
  row.update(sandbox_id=sid,api_ms=(time.perf_counter_ns()-start)/1e6);save(out.with_suffix('.ledger'),dict(product=name,sandbox_id=sid))
  attempts=0
  while True:
   attempts+=1
   try:
    if c['kind']=='e2b':
     r=s.commands.run(command,user='root',timeout=60);assert r.exit_code==0;r=r.stdout.strip()
    else:r=call(c['ctl']+['exec',s,'--insecure','--','/bin/sh','-c',command])
    assert r==marker,(r,marker)
    break
   except Exception:
    if attempts>=40:raise
    time.sleep(.1)
  row.update(ready_ms=(time.perf_counter_ns()-start)/1e6,attempts=attempts,success=True)
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
 p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('--worker');p.add_argument('--out',type=Path);a=p.parse_args();cfg=json.loads(a.config.read_text())
 if a.worker:return 0 if worker(a.worker,cfg,a.out) else 1
 names=[n for n in cfg if not n.startswith('_')];assert len(names)==6,'exactly six configured products required'
 assert a.out is not None;a.out.mkdir(parents=True,exist_ok=False);save(a.out/'config-public.json',{k:{x:y for x,y in v.items() if x!='key_file'} if isinstance(v,dict) else v for k,v in cfg.items()})
 samples={n:[] for n in names}
 lock=(ROOT/'results/startup.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 def run_one(n,i):
  out=a.out/f'{i+1:02d}-{n}.json'
  with (a.out/f'{i+1:02d}-{n}.log').open('w') as log:
   subprocess.run(['nsenter','--net=/run/netns/'+cfg[n]['netns'],sys.executable,str(Path(__file__).resolve()),str(a.config),'--worker',n,'--out',str(out)],stdout=log,stderr=log,check=True)
  return json.loads(out.read_text())['ready_ms']
 for r in range(5):
  for n in names[r%6:]+names[:r%6]:
   save(a.out/f'round{r+1}-{n}-host.json',dict(loadavg=Path('/proc/loadavg').read_text(),meminfo=Path('/proc/meminfo').read_text(),stat=Path('/proc/stat').read_text()))
   with cf.ThreadPoolExecutor(2) as pool:
    samples[n].extend(pool.map(lambda i:run_one(n,i),[2*r,2*r+1]))
   print('completed',n,len(samples[n]),flush=True)
   time.sleep(2) # outside measurement; allow asynchronous deletion/refill to settle
 save(a.out/'summary.json',{n:dict(n=len(v),median_ms=statistics.median(v),concurrency=2,min_ms=min(v),max_ms=max(v)) for n,v in samples.items()})
 return 0
if __name__=='__main__':sys.exit(main())
