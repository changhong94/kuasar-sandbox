import os,sys,json,time,uuid,subprocess,sqlite3,urllib.request,select,tempfile,pathlib,statistics,math,fcntl
os.environ.update(NO_PROXY='*',no_proxy='*')
from languages import print_command
R=pathlib.Path('/home/hong/src/research/startup-warm-repro-20261121');O=R/'results/startup';O.mkdir(exist_ok=True)
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
     with sqlite3.connect('file:/srv/fork2/data/base/node-ctl.db?mode=ro',uri=True) as db:
      rec=[json.loads(r[0]) for r in db.execute('select record from prepared_vm_leases')];n=db.execute('select count(*) from sandboxes').fetchone()[0]
     last={'leases':len(rec),'sandboxes':n};ok=len(rec)==64 and n==0
     if ok:
      logs=subprocess.check_output(['journalctl','--since','2 hours ago','--grep','prepared VM ready','-o','cat','--no-pager'],text=True)
      ok=all(v['run_id'] in logs for v in rec)
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
    import base64
    cat=json.load(open('/srv/fork2/data/image-templates/'+lang+'-warm512.json'))
    enc=cat['template']['templateID'][len('e2b-snp-'):];ref=base64.urlsafe_b64decode(enc+'='*(-len(enc)%4)).decode();loc=ref.split('@location:')[1]
    dirs=list(pathlib.Path('/srv/fork2/data/publications').glob('*/*/'+loc));assert len(dirs)==1
    paths=sorted(p for p in dirs[0].iterdir() if p.is_file())
    assert len(paths)>=2
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
   row['template']=tpl;row['start_unix_ns']=time.time_ns();start=time.perf_counter_ns()
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
def main():
 lock=open('/run/skyrl-threeway-benchmark.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 procs={};logs=[]
 try:
  for p in ['fork2','old','mlink']:
   a=([sys.executable] if p=='fork2' else ['nsenter','--net=/run/netns/'+('print113-old' if p=='old' else 'bench113-m-generic'),sys.executable])+[__file__,'worker',p]
   log=open(O/(p+'-client.log'),'w');logs.append(log);q=subprocess.Popen(a,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,bufsize=1);procs[p]=q;assert json.loads(q.stdout.readline())['ready']
  for lang in ['python','node','ruby']:
   ctl=['nsenter','--net=/run/netns/bench113-m-generic']+CFG['kuasar-mlink']['ctl']
   prep=time.monotonic_ns()
   for other in ['python','node','ruby']:
    if other!=lang:subprocess.run(ctl+['template','prewarm','disable',CFG['_languages'][other]['templates']['kuasar-mlink'],'--wait'],check=True,stdout=subprocess.DEVNULL)
   subprocess.run(ctl+['template','prewarm','set',CFG['_languages'][lang]['templates']['kuasar-mlink'],'--memory-state','full','--storage-min-ready','64','--storage-ready','64','--hot-ready-workers','0','--wait'],check=True,stdout=subprocess.DEVNULL)
   save(O/('preparation-mlink-'+lang+'.json'),{'elapsed_ms':(time.monotonic_ns()-prep)/1e6})
   for i in range(51):
    names=['fork2','old','mlink'];names=names[i%3:]+names[:i%3]
    for p in names:
     q=procs[p];q.stdin.write(json.dumps([lang,i])+'\n');q.stdin.flush();line=q.stdout.readline();v=json.loads(line);assert v['success'] and v['destroyed'] and not v['pool_error'],v
    print(lang,i,'of 50',flush=True)
  summary={}
  for lang in ['python','node','ruby']:
   summary[lang]={}
   for p in ['fork2','old','mlink']:
    rows=[json.load(open(O/f'{lang}-{p}-{i:02d}.json')) for i in range(1,51)]
    summary[lang][p]={'n':len(rows),**{k:{'median':statistics.median(v:=sorted(r[k] for r in rows)),'p95':v[math.ceil(.95*len(v))-1],'p99':v[math.ceil(.99*len(v))-1],'max':v[-1]} for k in ['api_ms','ready_ms','print_ms','interpreter_ms']}}
  save(O/'summary.json',summary);print(json.dumps(summary),flush=True)
 finally:
  for q in procs.values():
   if q.poll() is None:
    q.stdin.write('null\n');q.stdin.flush();q.wait(timeout=200)
  for l in logs:l.close()
if __name__=='__main__':
 if len(sys.argv)>1:worker(sys.argv[2])
 else:main()
