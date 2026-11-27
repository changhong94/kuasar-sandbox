#!/usr/bin/env python3
"""Task-owned native conductor/proxy/vswitch validation. Does not alter global sysctls."""
import threading
import argparse,base64,hashlib,json,os,pathlib,shutil,signal,socket,subprocess,re,tarfile,time,urllib.request,urllib.error,uuid
p=argparse.ArgumentParser();p.add_argument('--bin',required=True);p.add_argument('--work',required=True);p.add_argument('--image-file',required=True);p.add_argument('--remote',action='store_true');p.add_argument('--native-private',action='store_true');p.add_argument('--sdk-python');p.add_argument('--batch',action='store_true');p.add_argument('--memory-stress',action='store_true');p.add_argument('--fork-rounds',type=int,default=1);p.add_argument('--prepared-pool',action='store_true');p.add_argument('--pool-image-two');p.add_argument('--restart-controller',action='store_true');p.add_argument('--pause-resume',action='store_true');p.add_argument('--connected-udp',action='store_true');p.add_argument('--dynamic-memory',action='store_true');a=p.parse_args()
assert os.geteuid()==0,'root required'
assert 1<=a.fork_rounds<=10,'fork rounds must be 1..10'
assert not json.loads(subprocess.check_output(['ip','-j','route','show','exact','100.123.120.0/24'])),'test subnet is already in use'
bin=pathlib.Path(a.bin);work=pathlib.Path(a.work);work.mkdir(parents=True,exist_ok=False);os.chmod(work,0o700)
tag='kn'+uuid.uuid4().hex[:7];run=pathlib.Path('/run')/tag;run.mkdir(mode=0o700);switch=tag;ns=tag+'ns';mgmt=tag+'m0';unit=tag+'-runner@.service';unitpath=pathlib.Path('/run/systemd/system')/unit
slice_path=None;udp_socket=None;udp_thread=None;udp_stop=threading.Event();udp_peers={}
processes=[];ids=[];switchstarted=False;unitcreated=False;api_key='';base='';report={'backend':'native-private' if a.native_private else 'native-snapshot','remote':a.remote,'e2b_sdk':bool(a.sdk_python),'prepared_pool':a.prepared_pool}
def cmd(args,**kw):
 return subprocess.run(list(map(str,args)),check=True,timeout=120,**kw)
def output(args,**kw):
 try:return cmd(args,capture_output=True,text=True,**kw).stdout.strip()
 except subprocess.CalledProcessError as e:raise RuntimeError('command failed: '+e.stderr[-4000:]) from e
def save(name,obj):
 f=work/name;f.write_text(json.dumps(obj,indent=2));os.chmod(f,0o600);return f
def spawn(name,args,env=None):
 f=(work/(name+'.log')).open('wb');proc=subprocess.Popen(list(map(str,args)),stdout=f,stderr=f,env=env);processes.append((name,proc,f));return proc
def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def wait(test,timeout=30):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  if test():return
  for name,proc,_ in processes:
   if proc.poll()!=None:raise RuntimeError(name+' exited: '+(work/(name+'.log')).read_text()[-4000:])
  time.sleep(.1)
 raise TimeoutError('condition timed out')
def request(method,path,data=None):
 req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'X-API-Key':api_key,'Content-Type':'application/json'},method=method)
 try:
  with urllib.request.urlopen(req,timeout=120) as r:return json.load(r) if r.status!=204 else None
 except urllib.error.HTTPError as e:raise RuntimeError(f'{method} {path}: {e.code} {e.read().decode()}')
def getready(sid):
 v=request('GET','/sandboxes/'+sid)
 if v.get('state') in ('error','dead','stopped'):raise RuntimeError('sandbox failed: '+json.dumps(v))
 return v.get('state')=='running'
def sdk(sid,code,background=False,action="exec"):
 return output([a.sdk_python,pathlib.Path(__file__).with_name('sdk_exec.py')],input=json.dumps({'id':sid,'key':api_key,'api':base,'proxy':f'http://127.0.0.1:{pp}','code':code,'background':background,'action':action}))
def py(sid,code):
 if a.sdk_python:return sdk(sid,code)
 return output([bin/'sandbox-ctl','exec','--sandbox-id',sid,'--run-root',run/'sandboxes','--','/usr/local/bin/python3','-c',code])
try:
 # Each service uses a unique namespace and private socket/root. Pool zero starts
 # at most two task-owned VM runners; no shared test service is reconfigured.
 key=os.urandom(32).hex();env=os.environ.copy();env['MANIFEST_KEY']=key;env['PATH']=str(bin)+':'+env['PATH']
 secret=output([bin/'e2b-key-ctl','derive-api-secret'],env=env);env['API_SECRET']=secret
 api_key=output([bin/'e2b-key-ctl','gen-apikey'],env=env)
 sp=port();storecfg=save('store.json',{'listen':f'127.0.0.1:{sp}','backend':'fs','fs':{'root':str(work/'store'),'verify_content_key':True}})
 cmd([bin/'store-ctl','init','--config',storecfg,'--generation','G1'],capture_output=True)
 spawn('store',[bin/'store-ctl','serve','--config',storecfg])
 manifest=save('manifest.json',{'manifest':{'verify_content':True,'write_generation':'G1'},'store':{'endpoint':f'127.0.0.1:{sp}','pool':4,'timeout':'30s'},'cache':{'endpoint':''},'chunker':{'mode':'cdc'},'crypto':{'chunk':'aes','manifest':'aes'}})
 publications=work/'publications';location='source-python';digest=hashlib.sha256(location.encode()).hexdigest();imagepath=publications/digest[:2]/digest[2:4]/location;imagepath.mkdir(parents=True)
 image=imagepath/'root.image';shutil.copyfile(a.image_file,image)
 markers=[n for n in output(['tar','-tf',image]).splitlines() if n.startswith('.kuasar.digest.')]
 assert len(markers)==1
 ref='file://root.image@digest:'+markers[0].split('.')[-1]+'@location:'+location
 if a.remote:
  ref='manifest://'+output([bin/'manifest-ctl','store','--manifest-config',manifest,'file://'+str(image)+'@digest:'+markers[0].split('.')[-1]],env=env)
 template=('e2b' if a.sdk_python else 'bare')+'-img-'+base64.urlsafe_b64encode(ref.encode()).decode().rstrip('=')
 cmd(['ip','netns','add',ns]);cmd(['ip','-n',ns,'link','set','lo','up'])
 spawn('switch',[bin/'connector-ctl','vswitch','serve',switch,'--netns='+ns,'--ports='+('8' if a.prepared_pool else '4'),'--mac-addr=02:00:00:09:01:01','--port-mac-addr=per-port','--floating-ip-base=100.123.120.0','--mode=tap','--mgmt-extract=:'+mgmt+':169.254.169.250,0.0.0.0/0','--tapfd-listen='+str(run/'tapfd.sock'),'--watch-interval=2s'])
 switchstarted=True
 wait(lambda:(run/'tapfd.sock').exists())
 cmd(['ip','addr','add','169.254.169.250/32','dev',mgmt]);cmd(['ip','route','add','100.123.120.0/24','dev',mgmt])
 (work/'base').mkdir(mode=0o700)
 ap=port();pp=port();base=f'http://127.0.0.1:{ap}'
 cfg=save('conductor.json',{'api':{'domain':'migration.local','listen':f'127.0.0.1:{ap}'},'proxy':{'auth':'enforce'},'encryption_key':os.urandom(32).hex(),'manifest_config':str(manifest),'paths':{'run_root':str(run),'base_root':str(work/'base'),'config_socket':str(run/'node.sock')},'units':{'install':False,'runner_pools':([{'unit':unit,'size':2,'prepared_vm':True,'name':'prepared'},{'unit':unit,'size':0,'name':'cold'}] if a.prepared_pool else [{'unit':unit,'size':0}]),'builder_pools':[{'unit':tag+'-builder@.service','size':0}]},'sandbox':{'private_ram_fork':a.native_private,'timeout_sec':300,'resources':{'capacity':{'cpu':1,'memory':'512MiB'},'allocatable':{'cpu':1,'memory':'512MiB'}},'network':{'switch':switch,'tapfd_socket':str(run/'tapfd.sock'),'bare':{'inner_ip':'169.254.1.1/31','nexthop':'169.254.1.0'},'e2b':{'inner_ip':'169.254.0.21/30','nexthop':'169.254.0.22'}},'boot':{'kernel':str(bin/'vmlinux'),'runtime':str(bin/'sandbox-runtime.bundle'),'overlay_diff_template':'mkfs://ext4?size=256MiB'}},'checkpoint':{'mode':'local','remote':{'ref_location_parent':'' if a.remote else publications.as_uri()}}})
 if a.dynamic_memory:
  assert not a.prepared_pool,'dynamic admission test uses ordinary runners'
  document=json.loads(cfg.read_text())
  document['sandbox']['resources']['allocatable']['memory']='256MiB'
  document['sandbox']['resources']['startup']={'memory':'384MiB'}
  document['resource_listen']={'enabled':True,'socket':str(run/'resource.sock'),'cgroup_scan_paths':['/sys/fs/cgroup/sandbox.slice/sandbox-runner.slice'],'pools':[{'name':'default','capacity':{'cpu':4,'memory':'3GiB'},'allocatable':{'cpu':4,'memory':'3GiB'}}]}
  cfg.write_text(json.dumps(document))
 with unitpath.open('x') as f:f.write(f'''[Unit]\nCollectMode=inactive-or-failed\n[Service]\nType=exec\nWorkingDirectory={run}\nEnvironment=PATH={bin}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\nExecStart={bin}/node-ctl run-sandbox --pidfile={run}/runners/%i.pid --config-socket={run}/node.sock --run-id=%i\nRestart=no\nKillMode=control-group\nTimeoutStopSec=20\nSlice=sandbox-runner.slice\nDelegate=yes\n''')
 unitcreated=True
 cmd(['systemctl','daemon-reload'])
 if slice_path is not None:cmd(['systemctl','start','sandbox-runner-'+tag+'.slice'])
 spawn('conductor',[bin/'node-ctl','conductor','serve','--config',cfg],env)
 wait(lambda:(run/'node.sock').exists())
 cmd([bin/'node-ctl','manifest-key','add','--socket',run/'node.sock'],env=env,capture_output=True)
 proxy=save('proxy.json',{'config_socket':str(run/'node.sock'),'paths':{'run_root':str(run/'proxy')},'data_listen':f'127.0.0.1:{pp}','stats_socket':str(run/'proxy-stats.sock'),'shm_path':str(run/'routes.shm'),'route_capacity':64,'workers':1,'auth':'enforce','park_timeout':'30s'})
 spawn('proxy',[bin/'node-ctl','proxy','serve','--config',proxy],env)
 wait(lambda:(run/'proxy-stats.sock').exists())
 workload="import json,os,time,uuid\ni=uuid.uuid4().hex\nn=0\nwhile True:\n with open('/tmp/progress.next','w') as f:json.dump(dict(identity=i,counter=n,pid=os.getpid()),f)\n os.replace('/tmp/progress.next','/tmp/progress.json')\n n+=1\n time.sleep(.02)"
 if a.memory_stress:
  workload=workload.replace("n=0\nwhile True:","n=0\npayload=bytearray(16*1024*1024)\nwhile True:\n for off in range(0,len(payload),4096):payload[off]=n%251\n assert all(payload[off]==n%251 for off in range(0,len(payload),4096)), 'snapshot memory changed'\n")
 if a.prepared_pool:
  assert a.sdk_python,'prepared pool test uses E2B profile'
  wait(lambda:output(['journalctl','--no-pager','-o','cat','-u',tag+'-runner@*.service']).count('prepared VM ready')>=2,90)
 parent=request('POST','/sandboxes',{'templateID':template,'timeout':300,'metadata':{} if a.sdk_python else {'kuasar-sandbox.launch':json.dumps({'exec':'/usr/local/bin/python3','args':['-u','-c',workload],'restart':'never','cgroup_control':True})}})
 sid=parent['sandboxID'];ids.append(sid);wait(lambda:getready(sid),90)
 if a.sdk_python:sdk(sid,workload,background=True)
 wait(lambda:py(sid,"import os;print(os.path.exists('/tmp/progress.json'))")=='True',20)
 if a.sdk_python:sdk(sid,'captured-via-sdk',action='file-write')
 before=json.loads(py(sid,"print(open('/tmp/progress.json').read())"));py(sid,"open('/root/value','w').write('captured')")
 sqlprefix="import sqlite3; db=sqlite3.connect('/root/transactions.db'); db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA synchronous=FULL'); "
 py(sid,sqlprefix+"db.execute('CREATE TABLE state (v INTEGER)'); db.execute('INSERT INTO state VALUES (1)'); db.commit(); db.close()")
 def dbvalue(identity):return py(identity,sqlprefix+"print(db.execute('SELECT v FROM state').fetchone()[0]); db.close()")


 if a.connected_udp:
  udp_socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp_socket.bind(('169.254.169.250',0));udp_socket.settimeout(.2)
  def echo_udp():
   while not udp_stop.is_set():
    try:
     payload,peer=udp_socket.recvfrom(4096);udp_peers[payload.decode()]=peer;udp_socket.sendto(payload,peer)
    except socket.timeout:continue
    except OSError:
     if udp_stop.is_set():return
     raise
  udp_thread=threading.Thread(target=echo_udp);udp_thread.start()
  worker="import socket,time,os,json\ns=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)\ns.connect(('169.254.169.250',"+str(udp_socket.getsockname()[1])+") )\ns.settimeout(2)\nlast=''\nwhile True:\n try:\n  token=open('/tmp/udp-request').read()\n  if token!=last:\n   s.send(token.encode());answer=s.recv(4096).decode()\n   with open('/tmp/udp-next','w') as f:json.dump(dict(token=answer,pid=os.getpid()),f)\n   os.replace('/tmp/udp-next','/tmp/udp-response');last=token\n except (FileNotFoundError,socket.timeout):pass\n time.sleep(.01)"
  udp_pid=int(py(sid,"import subprocess; p=subprocess.Popen(['/usr/local/bin/python3','-u','-c',"+repr(worker)+"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);print(p.pid)"))
  def check_udp(identity):
   token=uuid.uuid4().hex
   py(identity,"open('/tmp/udp-request','w').write("+repr(token)+")")
   def answered():
    raw=py(identity,"import os;print(open('/tmp/udp-response').read() if os.path.exists('/tmp/udp-response') else '{}')")
    value=json.loads(raw)
    return value.get('token')==token and value.get('pid')==udp_pid
   wait(answered,10)
   assert token in udp_peers
   return udp_peers[token]
  parent_udp_peer=check_udp(sid)

 if a.restart_controller:
  # Restart only this test's controller. VM runners/proxy/store stay alive;
  # durable ownership must retain claimed VMs and recover the idle reserve.
  controller=next(entry for entry in processes if entry[0]=='conductor')
  controller[1].terminate();controller[1].wait(timeout=30)
  processes.remove(controller);controller[2].close()
  (work/'conductor.log').rename(work/'conductor-before-restart.log')
  spawn('conductor',[bin/'node-ctl','conductor','serve','--config',cfg],env)
  def recovered():
   try:return getready(sid)
   except (OSError,RuntimeError):return False
  wait(recovered,60)
  after_restart=json.loads(py(sid,"print(open('/tmp/progress.json').read())"))
  assert after_restart['identity']==before['identity'] and after_restart['pid']==before['pid'],'controller restart replaced the guest process'
  assert after_restart['counter']>before['counter'],'guest did not keep running'
  assert dbvalue(sid)=='1','controller restart lost SQLite state'
  report['controller_restart_preserved_process_and_storage']=True

 rounds=[];print_rounds=[]
 for index in range(a.fork_rounds-1):
  tick=time.monotonic()
  temporary=json.loads(sdk(sid,'',action='fork')) if a.sdk_python else request('POST','/sandboxes/'+sid+'/fork',{'timeout':300})[0]['sandbox']
  tid=temporary['sandboxID'];ids.append(tid);wait(lambda:getready(tid),90)
  rounds.append((time.monotonic()-tick)*1000)
  marker="native-"+uuid.uuid4().hex
  assert py(tid,"print("+repr(marker)+")")==marker
  print_rounds.append((time.monotonic()-tick)*1000)
  assert py(tid,"print(open('/root/value').read())")=='captured'
  progress=json.loads(py(tid,"print(open('/tmp/progress.json').read())"));assert progress['identity']==before['identity']
  time.sleep(.1)
  assert json.loads(py(tid,"print(open('/tmp/progress.json').read())"))['counter']>progress['counter']
  request('DELETE','/sandboxes/'+tid);ids.remove(tid)
 report['preceding_fork_ready_ms']=rounds
 report['preceding_request_to_print_ms']=print_rounds
 started=time.monotonic()
 if a.batch:
  children=request('POST','/sandboxes/'+sid+'/fork',{'timeout':300,'count':2})
  assert len(children)==2 and all('sandbox' in c for c in children),children
  child=children[0]['sandbox'];sibling=children[1]['sandbox']['sandboxID'];ids.append(sibling)
 else:child=json.loads(sdk(sid,'',action='fork')) if a.sdk_python else request('POST','/sandboxes/'+sid+'/fork',{'timeout':300})[0]['sandbox']
 cid=child['sandboxID'];ids.append(cid);report['fork_api_ms']=(time.monotonic()-started)*1000
 wait(lambda:getready(cid),90);report['fork_ready_ms']=(time.monotonic()-started)*1000
 marker='native-'+uuid.uuid4().hex
 assert py(cid,'print('+repr(marker)+')')==marker
 report['request_to_print_ms']=(time.monotonic()-started)*1000
 if a.batch:
  assert getready(sibling),'batch returned before readiness'
  assert json.loads(py(sibling,"print(open('/tmp/progress.json').read())"))['identity']==before['identity']
  assert py(sibling,"print(open('/root/value').read())")=='captured'
  if not a.native_private:assert (work/'conductor.log').read_text().count('phase=capture_and_parent_resume')==a.fork_rounds
  request('DELETE','/sandboxes/'+sibling);ids.remove(sibling);report['batch_two_independent_children' if a.native_private else 'batch_two_single_capture']=True
 after=json.loads(py(sid,"print(open('/tmp/progress.json').read())"));inherited=json.loads(py(cid,"print(open('/tmp/progress.json').read())"))
 assert before['identity']==after['identity']==inherited['identity'];assert after['counter']>before['counter'];assert before['pid']==inherited['pid']
 assert py(cid,"print(open('/root/value').read())")=='captured'
 if a.sdk_python:
  assert sdk(cid,'',action='file-read')=='captured-via-sdk'
  sdk(cid,'child-via-sdk',action='file-write');sdk(sid,'parent-via-sdk',action='file-write')
  assert sdk(cid,'',action='file-read')=='child-via-sdk'
  assert sdk(sid,'',action='file-read')=='parent-via-sdk'
  report['sdk_file_isolation']=True
  req=urllib.request.Request(f'http://127.0.0.1:{pp}/health',headers={'E2b-Sandbox-Id':cid,'E2b-Sandbox-Port':'49983','X-Access-Token':parent['envdAccessToken']})
  try:
   with urllib.request.urlopen(req,timeout=10) as response:raise AssertionError('parent credential accepted by child proxy')
  except urllib.error.HTTPError as error:assert error.code==401,error.code
  report['parent_token_rejected_by_child']=True
 if a.connected_udp:
  child_udp_peer=check_udp(cid);assert check_udp(sid)==parent_udp_peer
  assert child_udp_peer[0]!=parent_udp_peer[0],(child_udp_peer,parent_udp_peer)
  report['connected_udp_parent_child_distinct_peer']=True
 assert dbvalue(cid)=='1'
 py(cid,sqlprefix+"db.execute('UPDATE state SET v=2'); db.commit(); db.close()")
 py(sid,sqlprefix+"db.execute('UPDATE state SET v=3'); db.commit(); db.close()")
 assert dbvalue(cid)=='2' and dbvalue(sid)=='3'
 report['sqlite_full_sync_transactions_isolated']=True
 py(cid,"open('/root/value','w').write('child')");py(sid,"open('/root/value','w').write('parent')")
 assert py(cid,"print(open('/root/value').read())")=='child';assert py(sid,"print(open('/root/value').read())")=='parent'
 if a.pause_resume:
  captured_progress=json.loads(py(cid,"print(open('/tmp/progress.json').read())"))
  pause_start=time.monotonic();request('POST','/sandboxes/'+cid+'/pause',{'memory':True})
  report['pause_save_ms']=(time.monotonic()-pause_start)*1000
  resume_start=time.monotonic();request('POST','/sandboxes/'+cid+'/connect',{'timeout':300});wait(lambda:getready(cid),90)
  assert py(cid,"print(open('/root/value').read())")=='child' and dbvalue(cid)=='2'
  resumed_progress=json.loads(py(cid,"print(open('/tmp/progress.json').read())"))
  assert resumed_progress['identity']==captured_progress['identity'] and resumed_progress['pid']==captured_progress['pid']
  assert resumed_progress['counter']>=captured_progress['counter']
  report['resume_to_checked_python_ms']=(time.monotonic()-resume_start)*1000
  report['pause_resume_inherited_process']=True
 request('DELETE','/sandboxes/'+sid);ids.remove(sid);assert py(cid,"print(open('/root/value').read())")=='child'

 grand=json.loads(sdk(cid,'',action='fork')) if a.sdk_python else request('POST','/sandboxes/'+cid+'/fork',{'timeout':300})[0]['sandbox'];gid=grand['sandboxID'];ids.append(gid);wait(lambda:getready(gid),90)
 assert py(gid,"print(open('/root/value').read())")=='child'
 assert dbvalue(gid)=='2'
 if a.connected_udp:
  assert check_udp(gid)[0]!=check_udp(cid)[0]
  report['connected_udp_second_generation']=True
 request('DELETE','/sandboxes/'+cid);ids.remove(cid)
 assert py(gid,"print(open('/root/value').read())")=='child'
 assert dbvalue(gid)=='2'
 if a.memory_stress:
  first=json.loads(py(gid,"print(open('/tmp/progress.json').read())"));time.sleep(.2)
  last=json.loads(py(gid,"print(open('/tmp/progress.json').read())"));assert last['counter']>first['counter'],'memory stress process stopped'
  report['memory_stress_16mib']=True
 if a.prepared_pool:
  request('POST','/sandboxes/'+gid+'/pause',{'memory':False})
  exported=request('POST','/sandboxes/'+gid+'/export',{'toTemplate':True,'keepSource':True})
  fresh=request('POST','/sandboxes',{'templateID':exported['result'],'timeout':300})
  fid=fresh['sandboxID'];ids.append(fid);wait(lambda:getready(fid),90)
  assert fid.startswith('sr-'),'Sandbox artifact bypassed prepared assignment'
  assert py(fid,"print(open('/root/value').read())")=='child'
  assert dbvalue(fid)=='2'
  py(fid,"open('/root/value','w').write('from-portable-template')")
  request('DELETE','/sandboxes/'+fid);ids.remove(fid)
  report['pooled_sandbox_artifact_create']=True
 request('DELETE','/sandboxes/'+gid);ids.remove(gid)
 assert not (work/'base'/'fork-captures').exists() or not list((work/'base'/'fork-captures').iterdir()),'unpublished capture staging leaked'
 report['capture_staging_reclaimed']=True
 phases=[line.split('phase=',1)[1].split()[0] for line in (work/'conductor.log').read_text().splitlines() if 'fork phase' in line and 'phase=' in line]
 pending_resume=False;resumed_before_commit=0
 for phase in phases:
  if phase=='parent_route_resumed':
   assert not pending_resume,'duplicate parent resume'
   pending_resume=True
  elif phase=='capture_and_parent_resume':
   assert pending_resume,'parent route remained blocked through persistence'
   pending_resume=False;resumed_before_commit+=1
 assert a.native_private or (not pending_resume and resumed_before_commit>=2)
 report['parent_route_resumed_before_capture_commit']=resumed_before_commit

 if a.prepared_pool and a.pool_image_two:
  second=pathlib.Path(a.pool_image_two)
  markers2=[n for n in output(['tar','-tf',second]).splitlines() if n.startswith('.kuasar.digest.')]
  assert len(markers2)==1
  otherref='manifest://'+output([bin/'manifest-ctl','store','--manifest-config',manifest,'file://'+str(second)+'@digest:'+markers2[0].split('.')[-1]],env=env)
  othertemplate='e2b-img-'+base64.urlsafe_b64encode(otherref.encode()).decode().rstrip('=')
  other=request('POST','/sandboxes',{'templateID':othertemplate,'timeout':300})
  oid=other['sandboxID'];ids.append(oid);wait(lambda:getready(oid),90)
  assert oid.startswith('sr-')
  # Minimal BusyBox lacks the /usr/bin/ionice prerequisite of upstream envd.
  # Verify generic image binding through native exec; Python above separately
  # verifies the actual E2B SDK command path. Do not install a priority shim.
  assert output([bin/'sandbox-ctl','exec','--sandbox-id',oid,'--run-root',run/'sandboxes','--','/bin/busybox','echo','generic-pool-7841'])=='generic-pool-7841'
  request('DELETE','/sandboxes/'+oid);ids.remove(oid)
  report['same_pool_different_image_native_exec']=True
 report['second_generation_after_source_delete']=True
 journal=output(['journalctl','--no-pager','-o','cat','-u',tag+'-runner@*.service'])
 (work/'runners.log').write_text(journal)
 report['ch_pause_through_guest_reattach_ms']=[float(v) for v in re.findall(r'parent resumed before persistence pause_ms=([0-9.]+)',journal)]
 if a.prepared_pool:
  assert journal.count('prepared VM ready')>=3,'reserve was not replenished'
  assert 'prepared VM workload claimed' in journal,'Create bypassed prepared VM'
  assert 'prepared runtime incompatible' not in journal,'expected shape silently fell back to cold boot'
  report['pooled_create_and_refill']=True
 if a.dynamic_memory:
  assert 'initial cold Budget reserved=402653184' in journal
  assert 'memory: restore SafeTarget normalization accepted target=' in journal
  report['dynamic_memory_controller']=True
 report.update(passed=True,parent_continued=True,inherited_process_state=True,independent_files=True,independent_delete=True)
 print(json.dumps(report,indent=2))
finally:
 udp_stop.set()
 if udp_socket is not None:udp_socket.close()
 if udp_thread is not None:udp_thread.join(timeout=3)
 for sid in reversed(ids):
  try:request('DELETE','/sandboxes/'+sid)
  except Exception:pass
 if a.prepared_pool:
  # Stop this controller before its reserved runners, so intentional teardown
  # cannot start replacements behind the one-time unit inventory.
  for name,proc,_ in processes:
   if name=='conductor' and proc.poll() is None:
    proc.terminate()
    try:proc.wait(timeout=25)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
 if unitcreated:
  # Only our uniquely named units, never generic runners or other sessions.
  units=output(['systemctl','list-units','--all','--plain','--no-legend',tag+'-runner@*.service']).splitlines()
  for line in units:
   name=line.strip().split()[0]
   if name.startswith(tag+'-runner@'):cmd(['systemctl','stop',name],capture_output=True)
 for name,proc,f in reversed(processes):
  if proc.poll()==None:proc.terminate()
  try:proc.wait(timeout=25)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
  f.close()
 if switchstarted:
  subprocess.run([str(bin/'connector-ctl'),'vswitch','stop',switch],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
 subprocess.run(['ip','netns','del',ns],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 if slice_path is not None:
  cmd(['systemctl','stop','sandbox-runner-'+tag+'.slice'],capture_output=True);slice_path.unlink()
 if unitcreated:unitpath.unlink();cmd(['systemctl','daemon-reload'])
 save('result.json',report)
