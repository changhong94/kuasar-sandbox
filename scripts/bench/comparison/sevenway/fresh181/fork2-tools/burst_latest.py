import os
import sys,json,time,uuid,shlex,threading,concurrent.futures as cf,traceback,sqlite3,subprocess,os,fcntl,urllib.request,urllib.error,hashlib,resource
from pathlib import Path
os.environ.update(NO_PROXY='*',no_proxy='*')
from e2b import Sandbox
R=Path(sys.argv[1]);R.mkdir(parents=True,exist_ok=True);interval=int(sys.argv[2]);OUT=R/'requests';OUT.mkdir()
DB='/srv/fork2/data/base/node-ctl.db'
c=json.loads(Path('/srv/fork2/console.json').read_text());im=json.loads(Path('/srv/fork2/data/registry/python.json').read_text())
opts=dict(api_key=c['key'],api_url=c['api'],sandbox_url='http://127.0.0.1:19611')
lockfile=open('/run/skyrl-threeway-benchmark.lock','a');(None if os.environ.get("FORK2_FULL_LOCK_HELD")=="1" else fcntl.flock(lockfile,fcntl.LOCK_EX|fcntl.LOCK_NB))
def save(p,x):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(x,indent=2));q.replace(p)
def ids():
 with sqlite3.connect('file:'+DB+'?mode=ro',uri=True)as db:return {x[0]for x in db.execute('select id from sandboxes')}
def gate():
 t=time.monotonic()
 while time.monotonic()-t<300:
  with sqlite3.connect('file:'+DB+'?mode=ro',uri=True)as db:reserved={x[0]for x in db.execute('select run_id from prepared_vm_leases')}
  if len(reserved)==64:
   raw=subprocess.check_output(['curl','--fail','--silent','--show-error','--max-time','3','--unix-socket','/run/fork2/node.sock','http://localhost/internal/admin/resource-pressure'],timeout=5)
   pools=json.loads(raw).get('runner_pools',[])
   if any(p.get('idle_target')==64 and p.get('states',{}).get('idle')==64 and p.get('states',{}).get('starting',0)==0 for p in pools):return
  time.sleep(.2)
 raise TimeoutError('64 prepared slots not ready')
assert not ids(),'dedicated service contains pre-existing instances'
assert int(Path('/proc/meminfo').read_text().split('MemAvailable:')[1].split()[0])>64*1024**2
owned_records=R/'owned-records';owned_records.mkdir()
owned={};mutex=threading.Lock();rows=[];release=threading.Event();waiting=threading.Barrier(257);t0=None
result={'product':'fork2','interval_ms':interval,'requests':rows,'owned_remaining':[],'image_digest':im.get('manifest'),'pool_size':64,'prepare_concurrency':8,'retain_until_all_requests_finish':True,'cwd':'/','client_rlimit_nofile':resource.getrlimit(resource.RLIMIT_NOFILE)}
def persist():save(R/'owned.json',list(owned))
def task(i):
 waiting.wait();release.wait();delay=t0+i*interval/1000-time.perf_counter()
 if delay>0:time.sleep(delay)
 t=time.perf_counter();row={'index':i,'scheduled_ms':i*interval,'sent_ms':(t-t0)*1000,'success':False};marker='PRINT_'+uuid.uuid4().hex;native='READY_'+uuid.uuid4().hex;chunks=[];printed=[];ready=[]
 def got(x):
  chunks.append(x);z=''.join(chunks)
  if native+'\n'in z and not ready:ready.append(time.perf_counter())
  if marker+'\n'in z and not printed:printed.append(time.perf_counter())
 try:
  s=Sandbox.create(im['template_id'],timeout=600,**opts);row['sandbox_id']=s.sandbox_id;row['api_ms']=(time.perf_counter()-t)*1000
  track=time.perf_counter()
  with mutex:owned[s.sandbox_id]=s
  # Per-instance records keep crash cleanup discoverable without serializing
  # every create on rewriting the entire batch's ownership list. This IO
  # remains inside the measured path, before the first command.
  save(owned_records/(s.sandbox_id+'.json'),{'sandbox_id':s.sandbox_id})
  row['client_track_ms']=(time.perf_counter()-track)*1000
  command='printf "%s\\n" '+shlex.quote(native)+'; exec /usr/local/bin/python3 -c '+shlex.quote('import sys; print(sys.argv[1], flush=True)')+' '+shlex.quote(marker)
  row['command']=command
  r=s.commands.run(command,user='root',cwd='/',timeout=120,on_stdout=got)
  assert r.exit_code==0 and printed and ready,(r.exit_code,r.stderr)
  row.update(success=True,print_ms=(printed[0]-t)*1000,completed_ms=(printed[0]-t0)*1000,ready_ms=(ready[0]-t)*1000,marker=marker)
 except Exception:row['error']=traceback.format_exc()
 row['finished_ms']=(time.perf_counter()-t0)*1000
 save(OUT/f'{i:03}.json',row);return row
try:
 prep=time.perf_counter();gate();result['wait_for_initial_pool_ms']=(time.perf_counter()-prep)*1000
 result['binaries_sha256']={n:hashlib.sha256((Path('/srv/fork2/bin')/n).read_bytes()).hexdigest()for n in ['node-ctl','node-runner','node-vm-runner','sandbox-ctl','cloud-hypervisor']}
 result['controller_invocation']=subprocess.check_output(['systemctl','show','fork2-shared','-p','InvocationID','--value'],text=True).strip()
 with cf.ThreadPoolExecutor(256)as pool:
  futures=[pool.submit(task,i)for i in range(256)];waiting.wait();result['start_unix_ns']=time.time_ns();result['start_monotonic_ns']=time.monotonic_ns();t0=time.perf_counter();release.set()
  for future in cf.as_completed(futures):
   rows.append(future.result())
   if len(rows)%32==0:print('requests finished',len(rows),'success',sum(r['success']for r in rows),flush=True)
 result['all_requests_finished_ms']=(time.perf_counter()-t0)*1000
 good=sorted((r for r in rows if r['success']),key=lambda r:r['completed_ms']);result['successes']=len(good)
 result['total_to_last_successful_print_ms']=max((r['completed_ms']for r in good),default=None)
 result['all_256_print_ms']=result['total_to_last_successful_print_ms']if len(good)==256 else None
 result['completion_gaps_ms']=[r['completed_ms']-(good[i-1]['completed_ms']if i else 0)for i,r in enumerate(good)]
 result['send_span_ms']=max(r['sent_ms']for r in rows)-min(r['sent_ms']for r in rows)
 result['batch_valid']=len(good)==256
 persist()
 result['retained_db_ids']=sorted(ids());result['retained_verified_ids']=[];result['verification_errors']=[]
 def verify(item):
  sid,s=item
  try:
   token='ALIVE_'+sid;r=s.commands.run('printf '+shlex.quote('%s\n')+' '+shlex.quote(token)+' > /tmp/burst256-isolation; sync /tmp/burst256-isolation; cat /tmp/burst256-isolation',user='root',cwd='/',timeout=120)
   assert r.exit_code==0 and r.stdout.strip()==token
   return sid,None
  except Exception:return sid,traceback.format_exc()
 with cf.ThreadPoolExecutor(8)as pool:
  for sid,error in pool.map(verify,list(owned.items())):
   if error:result['verification_errors'].append({'id':sid,'error':error})
   else:result['retained_verified_ids'].append(sid)
 def read_back(item):
  sid,s=item
  r=s.commands.run('cat /tmp/burst256-isolation',user='root',cwd='/',timeout=120)
  assert r.exit_code==0 and r.stdout.strip()=='ALIVE_'+sid
  return sid
 with cf.ThreadPoolExecutor(8)as pool:
  result['isolation_verified_ids']=list(pool.map(read_back,list(owned.items())))
 result['isolation_verified']=len(result['isolation_verified_ids'])
 result['retained_verified']=len(result['retained_verified_ids'])
 print('retained verification',result['retained_verified'],'isolation',result['isolation_verified'],flush=True)
 fill=time.perf_counter();gate();result['reserve_refill_after_requests_ms']=(time.perf_counter()-fill)*1000
 result['retention_complete_unix_ns']=time.time_ns();save(R/'result.json',result)
except Exception:result['error']=traceback.format_exc()
finally:
 result['delete_started_unix_ns']=time.time_ns();result['delete_errors']=[]
 # Initially-empty dedicated service: include accepted objects whose create
 # response was lost. This list never includes another service's sandboxes.
 def delete(sid):
  try:
   if sid in owned:owned[sid].kill()
   else:
    req=urllib.request.Request(c['api']+'/sandboxes/'+sid,method='DELETE',headers={'X-API-Key':c['key']})
    with urllib.request.urlopen(req,timeout=120)as response:response.read()
   with mutex:owned.pop(sid,None);persist()
  except Exception:
   with mutex:result['delete_errors'].append({'id':sid,'error':traceback.format_exc()})
 all_ids=sorted(ids()|set(owned));survivors=all_ids[-2:]
 with cf.ThreadPoolExecutor(8)as pool:list(pool.map(delete,all_ids[:-2]))
 result['survivors_after_other_deletes']=[]
 for sid in survivors:
  if sid in owned:
   try:result['survivors_after_other_deletes'].append(read_back((sid,owned[sid])))
   except Exception:result.setdefault('survivor_errors',[]).append(traceback.format_exc())
 with cf.ThreadPoolExecutor(2)as pool:list(pool.map(delete,survivors))
 deadline=time.monotonic()+120
 while ids()and time.monotonic()<deadline:time.sleep(.2)
 result['owned_remaining']=sorted(ids());result['finish_unix_ns']=time.time_ns();save(R/'result.json',result)
 print(json.dumps({k:result.get(k)for k in ['successes','all_256_print_ms','total_to_last_successful_print_ms','retained_verified','owned_remaining']}),flush=True)
 if result['owned_remaining']:raise RuntimeError('unresolved owned instances')

if result.get('error') or result.get('successes')!=256 or result.get('retained_verified')!=256:raise RuntimeError('burst validation failed; inspect result.json')
