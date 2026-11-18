"""256 simultaneous client calls; retain all created sandboxes until all settle.

One excluded warmup. No admission throttling, no early deletion to free slots.
Capacity failures are results, not reasons to silently change the workload.
"""
from pathlib import Path
import argparse,concurrent.futures as cf,fcntl,json,os,resource,select,shlex,statistics,subprocess,sys,tempfile,threading,time,uuid
B=Path('/home/hong/src/research/pool-workers-113/64');T=Path('/home/hong/src/research/report-revision-113/tools');sys.path.insert(0,str(T))
from startup import setup
from languages import select_language,print_command
from pool_gate import wait
import runner as resources
N=256

def save(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2));tmp.replace(path)

def worker(product):
 cfg=select_language(json.loads((T/'config.json').read_text()),'python');c,Sandbox=setup(product,cfg)
 resources.pr=product;resources.setup(product)
 out=B/'results/burst256'/product;out.mkdir(parents=True,exist_ok=False)
 ctl=list(c.get('ctl',[]))
 if '--request-timeout' in ctl:
  i=ctl.index('--request-timeout');del ctl[i:i+2]
 if ctl:ctl+=['--request-timeout','120']
 def command(args,timeout=140):return subprocess.check_output(args,text=True,stderr=subprocess.PIPE,timeout=timeout).strip()
 def inventory():
  if product=='kuasar-fork':
   state=json.loads(Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json').read_text())
   return {sid for sid,r in state.items() if r.get('pool_state') not in ('ready','preparing','binding','quarantined','network_idle')}
  if ctl:
   rows=json.loads(command(ctl+['list','--json']))
   if isinstance(rows,dict):
    keys=[k for k in ('instances','items','sandboxes') if k in rows]
    assert len(keys)==1,('unknown mlink list envelope',list(rows))
    rows=rows[keys[0]]
   result=set()
   for row in rows:
    if isinstance(row,str):result.add(row);continue
    sid=next((row[k] for k in ('id','thinkactor_id','sandbox_id','sandboxID') if k in row),None)
    if sid is None:raise ValueError(('unknown mlink list identity fields',list(row)))
    result.add(sid)
   return result
  pager=Sandbox.list();ids=set()
  while pager.has_next:ids.update(s.sandbox_id for s in pager.next_items())
  return ids
 def create():
  if ctl:return command(ctl+['start',c['template'],'--insecure','--timeout','3600'])
  kw={**c.get('create_kwargs',{}),'timeout':3600,'request_timeout':120,'metadata':{'sixway.burst_id':batch}}
  return Sandbox.create(c['template'],**kw)
 def sid(s):return s if ctl else s.sandbox_id
 def destroy(s):
  if ctl:command(ctl+['delete',s])
  else:s.kill(request_timeout=120)
 def execute(s,row):
  native='NATIVE_'+uuid.uuid4().hex;marker='READY_'+uuid.uuid4().hex;cmd,_=print_command('python',marker,native);chunks=[]
  row.update(native_marker=native,print_marker=marker,command=cmd,exec_request_ns=time.monotonic_ns())
  def output(text):
   chunks.append(text);combined=''.join(chunks)
   if 'ready_ns' not in row and native+'\n' in combined:row['ready_ns']=time.monotonic_ns()
   if 'print_ns' not in row and marker+'\n' in combined:row['print_ns']=time.monotonic_ns()
  if ctl:
   with tempfile.TemporaryFile() as err:
    with subprocess.Popen(ctl+['exec',s,'--insecure','--user','root','--','/bin/bash','-l','-c',cmd],stdout=subprocess.PIPE,stderr=err) as proc:
     try:
      deadline=time.monotonic()+90
      while True:
       left=deadline-time.monotonic()
       if left<=0 or not select.select([proc.stdout],[],[],left)[0]:raise TimeoutError('burst print receipt')
       data=os.read(proc.stdout.fileno(),65536)
       if not data:break
       output(data.decode())
      assert proc.wait(timeout=10)==0
     except BaseException:proc.kill();proc.wait();raise
  else:
   result=s.commands.run(cmd,user='root',timeout=90,on_stdout=output)
   assert result.exit_code==0,result.stderr
  assert 'ready_ns' in row and 'print_ns' in row
  row['success']=True
 def verify_file(s,create=False):
  ident=sid(s)
  code=("import os,pathlib; p=pathlib.Path('/tmp/pool-capacity-isolation'); "
        + ("assert not p.exists(); f=p.open('w'); f.write("+repr(ident)+"); f.flush(); os.fsync(f.fileno()); f.close(); " if create else '')
        + "assert p.read_text()=="+repr(ident)+"; print("+repr(ident)+",flush=True)")
  ret=s.commands.run('/usr/local/bin/python3 -c '+shlex.quote(code),user='root',timeout=90)
  assert ret.exit_code==0 and ret.stdout.strip()==ident,(ret.stderr,ret.stdout)
 def check_alive(s):
  row={'id':sid(s),'alive':False}
  try:
   assert s.is_running()
   verify_file(s,create=True)
   row.update(alive=True,private_fsynced_file=True)
  except Exception as error:row.update(error_type=type(error).__name__,error=str(error)[:800])
  return row
 batch='burst256-'+uuid.uuid4().hex
 before=inventory();assert not before,('dedicated endpoint is not empty',len(before))
 gate=wait(c,64,600)
 # A disposable excluded warmup, then fully refill before the actual burst.
 warm=create()
 try:
  warmrow={};execute(warm,warmrow);save(out/'warmup.json',warmrow)
 finally:destroy(warm)
 gate=wait(c,64,600);assert not inventory()
 mem_available=int(Path('/proc/meminfo').read_text().split('MemAvailable:')[1].split()[0])*1024
 growth=json.loads((Path('/home/hong/src/research/report-revision-113')/f'results/growth/{product}.json').read_text())
 levels={r['instances']:statistics.median(x['pss_mib'] for x in r['resources']) for r in growth['samples']}
 estimate=max(0,levels[50]-levels[0])/50*N*2**20
 assert mem_available>max(64*1024**3,estimate*1.5+32*1024**3),('insufficient host memory headroom',mem_available,estimate)
 event_path=Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json.pool-events.jsonl') if product=='kuasar-fork' else Path('/home/hong/data/mlink-generic/ttlet.log') if product=='kuasar-mlink' else None
 offset=event_path.stat().st_size if event_path else None;inode=event_path.stat().st_ino if event_path else None
 owned={};mutex=threading.Lock();barrier=threading.Barrier(N+1);rows=[]
 result={'product':product,'batch_id':batch,'requested':N,'pool_before':gate,'image_digest':cfg['_image_digest'],'hold_policy':'retain every created sandbox until all 256 requests settle; then verify liveness and delete','mem_available_before_bytes':mem_available,'memory_estimate_from_50_instance_growth_bytes':estimate,'client_workers':N,'client_rlimit_nofile':list(resource.getrlimit(resource.RLIMIT_NOFILE)),'cache_policy':'prepared product default path plus one excluded warmup; no per-request strict file-cache conditioning','create_request_timeout_seconds':120,'before_resources':resources.resources()}
 def request(index):
  row={'index':index,'success':False,'api_success':False}
  barrier.wait(timeout=120);row['dispatch_ns']=time.monotonic_ns()
  try:
   s=create();row.update(sandbox_id=sid(s),api_ns=time.monotonic_ns(),api_success=True)
   with mutex:owned[sid(s)]=s
   execute(s,row)
  except Exception as error:
   row.update(error_type=type(error).__name__,error=str(error)[:800])
   detail=getattr(error,'stderr',None)
   if detail:row['error_detail']=(detail.decode(errors='replace') if isinstance(detail,bytes) else str(detail))[-1600:]

  row['settled_ns']=time.monotonic_ns()
  return row
 try:
  with cf.ThreadPoolExecutor(N) as executor:
   futures=[executor.submit(request,i) for i in range(1,N+1)]
   result['start_unix_ns']=time.time_ns();result['start_ns']=time.monotonic_ns();barrier.wait(timeout=120)
   for future in cf.as_completed(futures):
    row=future.result();rows.append(row);save(out/f"{row['index']:03d}.json",row)
    with mutex:save(out/'owned.json',list(owned))
  result['all_requests_settled_ns']=time.monotonic_ns();result['requests']=sorted(rows,key=lambda r:r['index'])
  with cf.ThreadPoolExecutor(16) as executor:checks=list(executor.map(check_alive,list(owned.values())))
  result['retention_checks']=checks
  result['retained_alive_before_cleanup']=sorted(r['id'] for r in checks if r['alive'])
  result['retention_failed']=[r for r in checks if not r['alive']]
  result['all_returned_instances_retained']=not result['retention_failed']
  # Keep every successful instance alive while the 64 reserves are replenished.
  import urllib.request
  deadline=time.monotonic()+120
  while True:
   req=urllib.request.Request(c['api_url']+'/template-pool',headers={'X-API-Key':Path(c['key_file']).read_text().strip()})
   with urllib.request.urlopen(req,timeout=5) as response:pool_state=json.load(response)
   if pool_state['ready']==64 and not pool_state['preparing']:break
   if time.monotonic()>deadline:raise TimeoutError('reserve refill while all instances are retained')
   time.sleep(.05)
  result['pool_while_instances_retained']=pool_state
  assert pool_state['assigned']==len(owned) and pool_state['capacity_scope']=='unclaimed_reserves'
  records=json.loads(Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json').read_text())
  result['network_identity_counts']={key:len({records[ident][key] for ident in owned}) for key in ('ip','namespace','holder_pid')}
  assert all(n==len(owned) for n in result['network_identity_counts'].values())
  with cf.ThreadPoolExecutor(16) as executor:list(executor.map(verify_file,list(owned.values())))
  result['all_private_files_verified']=True
  result['peak_retained_resources']=resources.resources()
 finally:
  result['cleanup_started_ns']=time.monotonic_ns();result['cleanup_started_unix_ns']=time.time_ns();errors=[]
  # Cleanup starts only after all requests have settled, never to unblock them.
  def drop(item):
   ident,s=item
   try:
    destroy(s)
    with mutex:owned.pop(ident,None)
   except Exception as error:
    with mutex:errors.append({'id':ident,'error':str(error)[:500]})
  items=list(owned.items());half=len(items)//2
  with cf.ThreadPoolExecutor(8) as executor:list(executor.map(drop,items[:half]))
  result['survivors_verified_after_half_destroyed']=False
  try:
   with cf.ThreadPoolExecutor(16) as executor:list(executor.map(verify_file,[s for _,s in items[half:]]))
   result['survivors_verified_after_half_destroyed']=True
  except Exception as error:errors.append({'survivor_check':str(error)[:500]})
  with cf.ThreadPoolExecutor(8) as executor:list(executor.map(drop,list(owned.items())))
  result['cleanup_errors']=errors;result['owned_remaining']=list(owned)
  # Timed-out callers can still commit server-side after an initial empty
  # inventory. Drain late publications until inventory AND the ready gate
  # are stable; preserve every late ID as evidence, never count it as print.
  unexpected=set();cleanup_deadline=time.monotonic()+600;stable=0
  result['cleanup_drain_observations']=[]
  while time.monotonic()<cleanup_deadline:
   remaining=inventory();late=remaining-set(owned);unexpected.update(late)
   result['cleanup_drain_observations'].append({'monotonic_ns':time.monotonic_ns(),'public_count':len(remaining),'late_ids':sorted(late)})
   def drop_late(ident):
    try:
     s=ident if ctl else Sandbox.connect(ident,timeout=3600,request_timeout=120)
     destroy(s)
    except Exception as error:
     with mutex:errors.append({'id':ident,'error':str(error)[:500]})
   with cf.ThreadPoolExecutor(8) as executor:list(executor.map(drop_late,sorted(late)))
   try:gate_after=wait(c,64,2)
   except TimeoutError:stable=0;continue
   if not inventory():
    stable+=1
    if stable>=3:
     result['pool_after']=gate_after;break
   else:stable=0
   time.sleep(1)
  result['unexpected_after_cleanup']=sorted(unexpected)
  result['public_remaining']=sorted(inventory())
  result['cleanup_ended_ns']=time.monotonic_ns()
  result['cleanup_quiescence_verified']=stable>=3
  result['end_unix_ns']=time.time_ns();result['end_ns']=time.monotonic_ns()
  if event_path:
   assert event_path.stat().st_ino==inode,'event log rotated during batch'
   with event_path.open('rb') as stream:stream.seek(offset);(out/'pool-events.jsonl').write_bytes(stream.read())
  result['requests']=sorted(rows,key=lambda r:r['index'])
  for key in ('api','ready','print'):
   completions=sorted(r[key+'_ns'] for r in rows if key+'_ns' in r)
   result[key]={'completed':len(completions),'completion_ms':[(t-result['start_ns'])/1e6 for t in completions],'adjacent_completion_gap_ms':[(b-a)/1e6 for a,b in zip(completions,completions[1:])],'all_256_ms':(completions[-1]-result['start_ns'])/1e6 if len(completions)==N else None,'last_success_ms':(completions[-1]-result['start_ns'])/1e6 if completions else None}
  dispatch=[r['dispatch_ns'] for r in rows]
  result['client_dispatch_spread_ms']=(max(dispatch)-min(dispatch))/1e6 if dispatch else None
  result['all_requests_settled_ms']=(result.get('all_requests_settled_ns',result['cleanup_started_ns'])-result['start_ns'])/1e6
  result['failed_requests']=sum(not r['success'] for r in rows)
  result['batch_valid']=len(rows)==N and not result['public_remaining'] and not result['owned_remaining'] and not errors and result['cleanup_quiescence_verified']
  save(out/'result.json',result);save(out/'owned.json',list(owned))
 assert result['batch_valid'],('burst cleanup/collection invalid',product)
 print(product,'print completions',result['print']['completed'],'of',N,'all ms',result['print']['all_256_ms'],flush=True)

if __name__=='__main__':
 soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
 assert hard==resource.RLIM_INFINITY or hard>=8192
 resource.setrlimit(resource.RLIMIT_NOFILE,(max(soft,8192),hard))
 with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  worker('kuasar-fork')
 result=json.loads((B/'results/burst256/kuasar-fork/result.json').read_text())
 assert result['print']['completed']==256 and result['api']['completed']==256
 assert result['all_returned_instances_retained'] and result['all_private_files_verified'] and result['survivors_verified_after_half_destroyed']
 save(B/'complete.json',{'success':True,'completed_unix':time.time()})
