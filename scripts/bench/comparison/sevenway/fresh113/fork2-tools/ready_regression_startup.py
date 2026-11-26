import os,sys,json,time,uuid,subprocess,sqlite3,urllib.request,select,tempfile,pathlib,statistics,math,fcntl
os.environ.update(NO_PROXY='*',no_proxy='*')
from languages import print_command
R=pathlib.Path('/home/hong/src/research/sevenway-current-20261126/fork2');O=R/'results/ready-template-detail/fixed';O.mkdir(parents=True,exist_ok=True)
CFG=json.load(open('/home/hong/src/research/sixway-full-20261119/tools/config.json'))
def save(p,x):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(x,indent=2));q.replace(p)
def jget(url,key=None):
 return json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'X-API-Key':key} if key else {}),timeout=5))
def worker(product):
 from e2b import Sandbox
 if product=='fork2':
  co=json.load(open('/srv/fork2/console.json'));opts=dict(api_key=co['key'],api_url=co['api'],sandbox_url='http://127.0.0.1:19211')
 elif product=='old':
  key=pathlib.Path('/home/hong/src/research/fork2-print-compare-113/old/deploy/api-key').read_text().strip();opts=dict(api_key=key,api_url='http://127.0.0.1:18887',sandbox_url='http://127.0.0.1:18887')
 else:ctl=CFG['kuasar-mlink']['ctl']
 def gate(lang):
  start=time.monotonic();last=None
  while time.monotonic()-start<180:
   try:
    if product=='old':
     last=jget(opts['api_url']+'/template-pool',key);ok=last['ready']==64 and last['assigned']==0 and last['preparing']==0
    elif product=='mlink':
     last=jget('http://127.0.0.1:29082/internal/status');t=next(t for t in last['templates'] if t['id']==CFG['_languages'][lang]['templates']['kuasar-mlink']);ok=last['capacity']['ready']==64 and last['capacity']['assigned']==0 and last['preparation']['profiles'].get('profile:2:2048')==64 and t['storage_ready']>=64 and t['storage_warming']==0 and t['memory_cache']['full']
    else:
     with sqlite3.connect('file:/home/hong/src/research/fork2-control-persistent/node-ctl.db?mode=ro',uri=True) as db:
      rec=[json.loads(r[0]) for r in db.execute('select record from prepared_vm_leases')];n=db.execute('select count(*) from sandboxes').fetchone()[0]
     last={'leases':len(rec),'sandboxes':n,'run_ids':[v['run_id'] for v in rec]};ok=len(rec)==64 and n==0
     if ok:
      pressure=json.loads(subprocess.check_output(['curl','-sf','--max-time','3','--unix-socket','/run/fork2/node.sock','http://localhost/internal/admin/resource-pressure']))
      ok=any(p.get('name')=='prepared' and p.get('states')=={'idle':64} for p in pressure['runner_pools'])
    if ok:return {'elapsed_ms':(time.monotonic()-start)*1000,'state':last}
   except Exception as e:last={'error':repr(e)}
   time.sleep(.1)
  raise TimeoutError((product,last))
 print(json.dumps({'ready':True}),flush=True)
 for line in sys.stdin:
  job=json.loads(line)
  if job is None:break
  lang,i=job;g=gate(lang)
  proof=None
  if product in ['old','fork2']:
   from cache_state import verified_warm
   if product=='old':
    prep=json.load(open('/home/hong/src/research/fork2-print-compare-113/old/data/adapter-state.json.snapshot-preparation.json'))
    directory=pathlib.Path(prep[{'python':'base','node':'node','ruby':'ruby'}[lang]]['directory'])
    paths=sorted(p for p in directory.iterdir() if p.is_file())
   else:
    mapping=json.loads((R/'results/ready-template-detail/template-backings.json').read_text())
    paths=[pathlib.Path(mapping[lang])]
    assert paths[0].is_file(), 'selected template backing missing'
   if i==0:
    # Normalize only this product's template RAM cache. Keep all catalogs and
    # generic slots. Never drop host-wide caches or unrelated files.
    if product=='fork2':
     reset=[pathlib.Path(p)for p in mapping.values()]
    else:
     reset=[pathlib.Path(v['directory'])/'memory-ranges'for v in prep.values()if isinstance(v,dict)and 'directory'in v]
    for p in reset:
     fd=os.open(p,os.O_RDONLY)
     try:os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED)
     finally:os.close(fd)
   proof=verified_warm(paths)
  marker='PRINT_'+uuid.uuid4().hex;native='READY_'+uuid.uuid4().hex;cmd,code=print_command(lang,marker,native);sid=None;s=None;chunks=[];ts={}
  row=dict(product=product,language=lang,iteration=i,warmup=i==0,digest=CFG['_languages'][lang]['digest'],command=cmd,pool_before=g,cache_preparation=proof,success=False)
  path=O/f'{lang}-{product}-{i:02d}.json'
  def got(x):
   chunks.append(x);txt=''.join(chunks)
   for k,v in [('ready_ms',native),('print_ms',marker)]:
    if v+'\n' in txt and k not in ts:ts[k]=(time.perf_counter_ns()-start)/1e6
  try:
   tpl=(json.load(open('/srv/fork2/data/registry/'+lang+'.json'))['template_id'] if product=='fork2' else {'python':'base','node':'node','ruby':'ruby'}[lang] if product=='old' else CFG['_languages'][lang]['templates']['kuasar-mlink'])
   row['template']=tpl;row['start_unix_ns']=time.time_ns();start=time.perf_counter_ns();row['start_monotonic_ns']=start
   if product!='mlink':s=Sandbox.create(tpl,timeout=300,**opts);sid=s.sandbox_id
   else:sid=subprocess.check_output(ctl+['start',tpl,'--insecure','--timeout','300'],text=True,stderr=subprocess.PIPE,timeout=90).strip()
   row['api_ms']=(time.perf_counter_ns()-start)/1e6;row['sandbox_id']=sid
   # Save recovery ledger outside measured interval only after receiving print.
   row['exec_start_ms']=(time.perf_counter_ns()-start)/1e6
   if product!='mlink':
    x=s.commands.run(cmd,user='root',cwd='/',on_stdout=got,timeout=60);assert x.exit_code==0,(x.exit_code,x.stderr)
   else:
    with tempfile.TemporaryFile() as err:
     p=subprocess.Popen(ctl+['exec',sid,'--insecure','--user','root','--','/bin/bash','-l','-c',cmd],stdout=subprocess.PIPE,stderr=err)
     deadline=time.monotonic()+60
     try:
      while True:
       remaining=deadline-time.monotonic()
       if remaining<=0 or not select.select([p.stdout],[],[],remaining)[0]:raise TimeoutError('stdout')
       b=os.read(p.stdout.fileno(),65536)
       if not b:break
       got(b.decode())
      assert p.wait(timeout=5)==0
     finally:
      if p.poll() is None:p.kill();p.wait()
   assert len(ts)==2 and ''.join(chunks).strip()==native+'\n'+marker, ''.join(chunks)
   row.update(ts,success=True,interpreter_ms=ts['print_ms']-ts['ready_ms'])
   diag=s.commands.run("dmesg | grep -E 'restore stages|workload launch' | tail -n 9",user='root',cwd='/',timeout=30)
   row['guest_diagnostics']=diag.stdout;row['guest_diagnostics_error']=diag.stderr
  except Exception as e:row['error']=repr(e)
  finally:
   save(path.with_suffix('.ledger'),{'sandbox_id':sid,'product':product})
   if sid:
    try:
     if s:s.kill()
     else:subprocess.run(ctl+['delete',sid],check=True,capture_output=True,timeout=60)
     row['destroyed']=True;path.with_suffix('.ledger').unlink()
    except Exception as e:row['destroyed']=False;row['delete_error']=repr(e)
   save(path,row)
  try:row['pool_after']=gate(lang)
  except Exception as e:row['pool_error']=repr(e)
  save(path,row);print(json.dumps({'success':row['success'],'destroyed':row.get('destroyed'),'pool_error':row.get('pool_error'),'file':str(path)}),flush=True)
if __name__=='__main__':worker(sys.argv[1] if len(sys.argv)>1 else 'fork2')
