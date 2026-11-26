"""256 real Python creates, all successes retained until every request finishes."""
import resource_worker181 as a
from languages import print_command
import concurrent.futures as cf,threading,time,json,uuid,sys,traceback
gap=int(sys.argv[2]);R=a.R/'measurements/burst'/a.product/str(gap);R.mkdir(parents=True,exist_ok=True)

# Retry cleanup of explicitly owned prior-batch IDs over a fresh HTTP/1 connection.
if a.Sandbox and a.product in ('fork2','kuasar-off','kuasar-uffd'):
 import urllib.request,urllib.error
 from pathlib import Path
 key=Path(a.c['key_file']).read_text().strip()
 for prior in sorted((a.R/'measurements/burst'/a.product).glob('*/result.json')):
  d=json.load(open(prior))
  if not d.get('owned_remaining'):continue
  evidence=prior.with_name('before-cleanup-retry.json')
  if not evidence.exists():a.b.save(evidence,d)
  for sid in list(d['owned_remaining']):
   req=urllib.request.Request(a.c['api_url']+'/sandboxes/'+sid,method='DELETE',headers={'X-API-Key':key})
   try:
    with urllib.request.urlopen(req,timeout=120) as response:assert response.status in (200,204)
   except urllib.error.HTTPError as e:
    if e.code!=404:raise
   d['owned_remaining'].remove(sid);(prior.parent/('owned-'+sid+'.json')).unlink(missing_ok=True)
   d.setdefault('cleanup_retried_ids',[]).append(sid);a.b.save(prior,d)

out=R/'result.json'
if out.exists():
 d=json.load(open(out))
 if d.get('measurement_complete') and not d.get('owned_remaining'):raise SystemExit(0)
 raise RuntimeError('Prior burst requires ownership audit before retry')
assert not list(R.glob('owned-*.json')),'Unresolved ownership records'
available=int(__import__('pathlib').Path('/proc/meminfo').read_text().split('MemAvailable:')[1].split()[0])
assert available>32*1024**2,'host memory guard'
if a.product=='kuasar-fork':
 import subprocess
 subprocess.run([sys.executable,str(a.R/'tools/legacy_pool181.py'),'kuasar-fork'],check=True)
if a.product=='fork2':
 conductor=json.load(open('/srv/fork2/conductor.json'))
 image_pool=[p for p in conductor['units']['runner_pools'] if p.get('prepared_vm') and not p.get('prepared_restore')]
 assert sum(p['size'] for p in image_pool)==64, 'Image burst requires 64 image-compatible generic slots; restore holders do not count'
if a.product=='kuasar-mlink':
 # Repair only an idle task-owned pool whose readiness accounting is incomplete.
 # This is preparation, before request timing; never restart assigned instances.
 import urllib.request,subprocess
 with urllib.request.urlopen(a.c.get('pool_status_url','http://127.0.0.1:29082/internal/status'),timeout=3) as response:
  before=json.load(response)
 cap=before['capacity'];prep=before['preparation']
 if cap.get('ready')!=64 or prep.get('profiles',{}).get('profile:2:2048',0)!=64:
  assert all(cap.get(k,0)==0 for k in ('assigned','waiters','preparing','rearming','recycling','retiring','failed'))
  a.b.save(R/'pool-repair-before.json',before)
  repair_started=time.monotonic()
  subprocess.run(['systemctl','restart','bench108-mlink'],check=True)
  a.wait(a.c)
  a.b.save(R/'pool-repair-preparation.json',{'elapsed_ms':(time.monotonic()-repair_started)*1000,'reason':'idle profile inventory incomplete'})
a.wait(a.c)
def server_ids():
 if a.product=='kuasar-fork':
  records=json.load(open('/opt/bench108/data/fork/adapter-state.json'))
  return {sid for sid,v in records.items() if v.get('pool_state') not in ('ready','preparing','reserved','idle','network_idle')}
 if not a.Sandbox:return set() # CLI ownership stays in per-request ledger.
 pager=a.Sandbox.list();ids=set()
 while pager.has_next:ids.update(x.sandbox_id for x in pager.next_items())
 return ids
assert not server_ids(),'dedicated endpoint has preexisting active sandboxes'
if a.Sandbox:
 for prior in sorted((a.R/'measurements/burst'/a.product).glob('*/result.json')):
  old=json.load(open(prior))
  if old.get('cleanup_retried_ids') and not old.get('owned_remaining'):
   old['server_remaining']=[]
   old['cleanup_inventory_verified_unix_ns']=time.time_ns()
   a.b.save(prior,old)

from pathlib import Path
event_path={'kuasar-fork':'/opt/bench108/data/fork/adapter-state.json.pool-events.jsonl','kuasar-mlink':'/opt/bench108/data/mlink/ttlet.log'}.get(a.product)
event_offset=Path(event_path).stat().st_size if event_path else None
owned={};mutex=threading.Lock();barrier=threading.Barrier(257);release=threading.Event();rows=[];t0=0
result=dict(product=a.product,requests=256,interval_ms=gap,pool_size=64,prepare_concurrency=8,image_digest=a.cfg['_languages']['python']['digest'],retain_until_all_requests_finish=True,measurement_complete=False)
def task(i):
 barrier.wait();release.wait();delay=t0+i*gap/1000-time.perf_counter()
 if delay>0:time.sleep(delay)
 start=time.perf_counter();row=dict(index=i,sent_ms=(start-t0)*1000,scheduled_ms=i*gap,success=False)
 marker='PRINT_'+uuid.uuid4().hex;native='READY_'+uuid.uuid4().hex;chunks=[];printed=[];ready=[]
 def received(v):
  chunks.append(v);z=''.join(chunks)
  if native+'\n' in z and not ready:ready.append(time.perf_counter())
  if marker+'\n' in z and not printed:printed.append(time.perf_counter())
 try:
  s=a.create();sid=a.b.sid(s);row.update(sandbox_id=sid,api_ms=(time.perf_counter()-start)*1000)
  with mutex:owned[sid]=s
  a.b.save(R/('owned-'+sid+'.json'),{'sandbox_id':sid})
  cmd,_=print_command('python',marker,native);row['command']=cmd
  if a.Sandbox:
   z=s.commands.run(cmd,user='root',cwd='/',timeout=120,on_stdout=received);assert z.exit_code==0,z.stderr
  else:a.stream_cmd(s,cmd,received)
  assert ready and printed
  row.update(success=True,marker=marker,ready_ms=(ready[0]-start)*1000,print_ms=(printed[0]-start)*1000,completed_ms=(printed[0]-t0)*1000)
 except Exception:row['error']=traceback.format_exc()
 row['finished_ms']=(time.perf_counter()-t0)*1000;a.b.save(R/f'request-{i:03}.json',row);return row
try:
 with cf.ThreadPoolExecutor(256) as p:
  futures=[p.submit(task,i)for i in range(256)];barrier.wait();result['start_unix_ns']=time.time_ns();t0=time.perf_counter();release.set()
  for f in cf.as_completed(futures):
   rows.append(f.result())
   if len(rows)%32==0:print(a.product,gap,len(rows),sum(x['success']for x in rows),flush=True)
 result['all_requests_finished_ms']=(time.perf_counter()-t0)*1000
 good=sorted((x for x in rows if x['success']),key=lambda x:x['completed_ms']);result['successes']=len(good)
 result['all_256_print_ms']=good[-1]['completed_ms']if len(good)==256 else None
 result['completion_gaps_ms']=[x['completed_ms']-(good[i-1]['completed_ms']if i else 0)for i,x in enumerate(good)]
 result['retained_ids']=sorted(owned);result['verified_ids']=[];result['verification_errors']=[]
 def verify(pair):
  sid,s=pair;token=uuid.uuid4().hex
  try:
   token='ISOLATION_'+sid
   assert a.cmd(s,'echo '+token+' > /tmp/burst-isolation; sync /tmp/burst-isolation; cat /tmp/burst-isolation')==token
   return sid,None
  except Exception as e:
   if a.Sandbox:
    import urllib.request,urllib.error
    from pathlib import Path
    with mutex:result.setdefault('cleanup_transport_errors',[]).append({'id':sid,'error':repr(e)})
    try:
     key=Path(a.c['key_file']).read_text().strip()
     req=urllib.request.Request(a.c['api_url']+'/sandboxes/'+sid,method='DELETE',headers={'X-API-Key':key})
     try:
      with urllib.request.urlopen(req,timeout=120) as response:assert response.status in (200,204)
     except urllib.error.HTTPError as error:
      if error.code!=404:raise
     return sid,None
    except Exception as retry_error:return sid,repr(retry_error)
   return sid,repr(e)
 with cf.ThreadPoolExecutor(8) as p:
  for sid,error in p.map(verify,list(owned.items())):
   if error:result['verification_errors'].append({'id':sid,'error':error})
   else:result['verified_ids'].append(sid)
 # Check all retained files again after every writer has completed.
 result['isolation_verified_ids']=[]
 for sid,s in list(owned.items()):
  if sid not in result['verified_ids']:continue
  try:
   assert a.cmd(s,'cat /tmp/burst-isolation')=='ISOLATION_'+sid
   result['isolation_verified_ids'].append(sid)
  except Exception as e:result['verification_errors'].append({'id':sid,'phase':'readback','error':repr(e)})
 result['isolation_passed']=all(x['sandbox_id'] in result['isolation_verified_ids'] for x in good)
 result['measurement_complete']=True
finally:
 result['cleanup_started_unix_ns']=time.time_ns()
 if a.Sandbox:
  try:
   extra=server_ids()-set(owned);result['accepted_without_client_handle']=sorted(extra)
   for sid in extra:owned[sid]=None
  except Exception:result['server_inventory_error']=traceback.format_exc()
 result['samples']=rows;result['owned_remaining']=list(owned);a.b.save(out,result)
 def destroy(pair):
  sid,s=pair
  try:
   if s is None:a.Sandbox.kill(sid)
   else:a.b.kill(s)
   return sid,None
  except Exception as e:return sid,repr(e)
 with cf.ThreadPoolExecutor(8) as p:
  for sid,error in p.map(destroy,list(owned.items())):
   if error:result.setdefault('cleanup_errors',[]).append({'id':sid,'error':error})
   else:owned.pop(sid);(R/('owned-'+sid+'.json')).unlink(missing_ok=True)
 result['owned_remaining']=list(owned);a.b.save(out,result)
 if not owned:result['pool_after']=a.wait(a.c,allow_surplus=a.product=='kuasar-mlink');a.b.save(out,result)
if event_path:
 with open(event_path,'rb') as f:
  f.seek(event_offset);(R/'pool-events.jsonl').write_bytes(f.read())
if a.product=='fork2':
 import subprocess
 raw=subprocess.check_output(['curl','-sf','--unix-socket','/run/fork2/node.sock','http://localhost/internal/admin/resource-pressure'])
 (R/'pool-history.json').write_bytes(raw)
if a.Sandbox:
 deadline=time.monotonic()+120
 while server_ids() and time.monotonic()<deadline:time.sleep(.2)
 result['server_remaining']=sorted(server_ids());a.b.save(out,result);assert not result['server_remaining']
assert not owned
print('BURST_COMPLETE',a.product,gap,result['successes'],flush=True)
