#!/usr/bin/env python3
"""Verify task-owned native guests before and after fork migration."""
import argparse,json,os,pathlib,selectors,signal,socket,socketserver,subprocess,sys,threading,time,uuid
p=argparse.ArgumentParser();p.add_argument('--bin',required=True);p.add_argument('--work',required=True);p.add_argument('--image',required=True);p.add_argument('--fork',action='store_true');p.add_argument('--remote',action='store_true');p.add_argument('--network',action='store_true');p.add_argument('--child-first',action='store_true');p.add_argument('--reject-sockets',action='store_true');p.add_argument('--tcp-state',action='store_true');p.add_argument('--tapfd',action='store_true');p.add_argument('--checkpoints',action='store_true');a=p.parse_args()
if a.tapfd and not (a.fork and a.network):p.error('--tapfd requires --fork --network')
if a.tcp_state and not (a.fork and a.network):p.error('--tcp-state requires --fork --network')
if a.reject_sockets and not (a.fork and a.network): p.error('--reject-sockets requires --fork --network')
if a.network:
 if not a.fork: p.error('--network currently tests only the migrated --fork path')
 if os.readlink('/proc/self/ns/net') == os.readlink('/proc/1/ns/net'):
  p.error('--network requires a private host network namespace')
bin=pathlib.Path(a.bin);work=pathlib.Path(a.work);work.mkdir(parents=True,exist_ok=False)
run=pathlib.Path('/run')/('kn-'+uuid.uuid4().hex[:8]);run.mkdir(mode=0o700)
manifest_cfg=None
tcp_server=None
tcp_connections=[]
taps=[]
processes={};report={'image':a.image,'mode':'unmodified upstream snapshot/restore'}
def command(args,**kw):
 try:return subprocess.run([str(x) for x in args],check=True,timeout=120,**kw)
 except subprocess.CalledProcessError as e:
  print('COMMAND FAILED',e.stdout,e.stderr,flush=True);raise
def start(sid,cfg,restore=None,parent=None,output=None):
 path=work/(sid+'.json');path.write_text(json.dumps(cfg));r,w=os.pipe()
 args=[bin/'sandbox-ctl','run','--config',path,'--sandbox-id',sid,'--run-root',run,'--base-root',work/'base','--ch-binary',bin/'cloud-hypervisor','--ready-fd',str(w),'--console','off']
 if a.checkpoints:args[2:2]=['--enable-checkpoint']
 if restore:args+=['--restore',restore]
 if parent:
  args[1]='fork';args=args[:-2];args+=['--parent-id',parent]+(['--upload'] if a.remote else ['--output',output])
 if manifest_cfg:args+=['--manifest-config',manifest_cfg]
 log=(work/(sid+'.log')).open('wb');proc=subprocess.Popen([str(x) for x in args],stdout=log,stderr=log,pass_fds=(w,));os.close(w);processes[sid]=(proc,log)
 sel=selectors.DefaultSelector();sel.register(r,selectors.EVENT_READ);data=b'';deadline=time.monotonic()+90
 try:
  while time.monotonic()<deadline:
   if proc.poll() is not None:raise RuntimeError(f'{sid} exited: '+(work/(sid+'.log')).read_text()[-5000:])
   if sel.select(.2):
    block=os.read(r,65536)
    if not block:raise RuntimeError(f'{sid}: readiness pipe closed')
    data+=block
    if b'ready' in data.splitlines():return
  raise TimeoutError(f'{sid}: readiness: {data!r}')
 finally:sel.close();os.close(r)
def stop(sid):
 proc,log=processes.pop(sid)
 if proc.poll() is None:proc.send_signal(signal.SIGTERM)
 try:proc.wait(timeout=30)
 except subprocess.TimeoutExpired:proc.kill();proc.wait();raise RuntimeError(f'{sid}: graceful close failed')
 finally:log.close()
def py(sid,code):
 return command([bin/'sandbox-ctl','exec','--sandbox-id',sid,'--run-root',run,'--','/usr/local/bin/python3','-c',code],capture_output=True,text=True).stdout.strip()
try:
 if a.remote:
  with socket.socket() as probe:
   probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
  endpoint='127.0.0.1:'+str(port)
  storecfg=work/'store.json';storecfg.write_text(json.dumps({'listen':endpoint,'backend':'fs','fs':{'root':str(work/'store-data'),'verify_content_key':True}}))
  command([bin/'store-ctl','init','--config',storecfg,'--generation','G1'],capture_output=True)
  log=(work/'store.log').open('wb');storeproc=subprocess.Popen([str(bin/'store-ctl'),'serve','--config',str(storecfg)],stdout=log,stderr=log);processes['store']=(storeproc,log)
  deadline=time.monotonic()+15
  while True:
   try:
    with socket.create_connection(('127.0.0.1',port),timeout=.2):break
   except OSError:
    if storeproc.poll() is not None or time.monotonic()>deadline:raise RuntimeError('isolated store failed')
    time.sleep(.05)
  manifest_cfg=work/'manifest.json'
  fd=os.open(manifest_cfg,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w') as f:json.dump({'manifest':{'key':os.urandom(32).hex(),'verify_content':True,'write_generation':'G1'},'store':{'endpoint':endpoint,'pool':4,'timeout':'30s'},'cache':{'endpoint':''},'chunker':{'mode':'cdc'},'crypto':{'chunk':'aes','manifest':'aes'}},f)
  report['storage']='Manifest CDC chunks, AES, isolated loopback filesystem store; no cache'
 if a.tcp_state:
  class Echo(socketserver.StreamRequestHandler):
   def handle(self):
    token=uuid.uuid4().hex
    tcp_connections.append((token,self.client_address[0]))
    try:
     while self.rfile.readline():self.wfile.write((token+'\n').encode());self.wfile.flush()
    except (ConnectionError,OSError):pass
  class TCPServer(socketserver.ThreadingTCPServer):
   daemon_threads=True
  tcp_server=TCPServer(('0.0.0.0',0),Echo)
  threading.Thread(target=tcp_server.serve_forever,daemon=True).start()
 image=work/'root.image'
 with image.open('wb') as dest, (work/'flatten.log').open('wb') as log:
  save=subprocess.Popen(['docker','save',a.image],stdout=subprocess.PIPE)
  flat=subprocess.run([str(bin/'flatten-ctl'),'export','--output',str(image),'--no-progress'],stdin=save.stdout,stdout=log,stderr=log)
  save.stdout.close();assert save.wait()==0 and flat.returncode==0,'flatten failed'
 markers=[name for name in command(['tar','-tf',image],capture_output=True,text=True).stdout.splitlines() if name.startswith('.kuasar.digest.')]
 assert len(markers)==1
 rootref='file://'+str(image)+'@digest:'+markers[0].split('.')[-1]
 disk=work/'disk-template.raw';command(['truncate','-s','256M',disk]);command(['mkfs.ext4','-q','-F',disk])
 workload="""import json,os,time,uuid
identity=uuid.uuid4().hex
counter=0
while True:
 with open('/tmp/progress.next','w') as f:json.dump(dict(identity=identity,counter=counter,pid=os.getpid()),f)
 os.replace('/tmp/progress.next','/tmp/progress.json')
 counter+=1
 time.sleep(.02)
"""
 if a.tcp_state:
  workload=workload.replace('identity=uuid.uuid4().hex',"import socket\nstream=None\npeer_token=''\nudp_token=''\nudp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); udp.bind(('0.0.0.0',0)); udp.setblocking(False)\nlistener=socket.socket(); listener.bind(('0.0.0.0',0)); listener.listen()\nidentity=uuid.uuid4().hex")
  workload=workload.replace('while True:',"""while True:
 try:udp_token=udp.recv(128).decode()
 except BlockingIOError:pass
 try:
  if stream is None:
   host='198.18.250.5' if open('/sys/class/net/eth0/address').read().strip().endswith(':02') else '198.18.250.1'
   stream=socket.create_connection((host,PORT),timeout=2)
  stream.sendall(b'heartbeat\\n')
  received=stream.recv(128)
  if not received:raise ConnectionError('EOF')
  peer_token=received.decode().strip()
 except OSError:
  if stream:stream.close()
  stream=None
""".replace('PORT',str(tcp_server.server_address[1])))
  workload=workload.replace('pid=os.getpid()',"pid=os.getpid(),peer_token=peer_token,random=os.urandom(32).hex(),listener_port=listener.getsockname()[1],udp_token=udp_token,udp_port=udp.getsockname()[1]")
  workload=workload.replace('identity=uuid.uuid4().hex',"local_listener=socket.socket(); local_listener.bind(('127.0.0.1',0)); local_listener.listen()\nlocal_client=socket.create_connection(local_listener.getsockname(),timeout=2)\nlocal_server,_=local_listener.accept(); local_server.settimeout(2)\nidentity=uuid.uuid4().hex")
  workload=workload.replace('while True:',"while True:\n local_client.sendall(b'x'); assert local_server.recv(1)==b'x'\n local_server.sendall(b'y'); assert local_client.recv(1)==b'y'")
 if a.reject_sockets:workload="import socket\nlistener=socket.socket(); listener.bind(('198.18.250.2',0)); listener.listen()\n"+workload
 cfg={'resources':{'capacity':{'cpu':1,'memory':'512MiB'},'allocatable':{'cpu':1,'memory':'512MiB'}},'boot':{'kernel':'file://'+str(bin/'vmlinux'),'runtime':'file://'+str(bin/'sandbox-runtime.bundle'),'root':{'base':rootref,'overlay':{'diff_template':'file://'+str(disk)}}},'launch':{'exec':'/usr/local/bin/python3','args':['-u','-c',workload],'restart':'never','cgroup_control':True}}
 if a.network:
  for name,addr in [('knp0','198.18.250.1/30'),('knc0','198.18.250.5/30')]:
   command(['ip','tuntap','add','dev',name,'mode','tap']);taps.append(name)
   command(['ip','addr','add',addr,'dev',name])
   if name=='knp0' or a.tapfd:command(['ip','link','set',name,'up'])
  cfg['network']={'tap':'knp0','interface':'eth0','ip':'198.18.250.2/30','mac':'02:aa:00:00:00:01','hostname':'native-parent'}
 start('parent',cfg)
 before=json.loads(py('parent',"import os,time\nfor _ in range(200):\n if os.path.exists('/tmp/progress.json'): break\n time.sleep(.01)\nprint(open('/tmp/progress.json').read())"))
 if a.tcp_state:
  deadline=time.monotonic()+10
  while not before.get('peer_token'):
   assert time.monotonic()<deadline
   time.sleep(.02);before=json.loads(py('parent',"print(open('/tmp/progress.json').read())"))
 py('parent',"open('/root/fork-value','w').write('before')")
 cap=work/'snapshot';cap.mkdir()
 childcfg={'resources':cfg['resources'],'boot':{'runtime':'file://'+str(bin/'sandbox-runtime.bundle')}}
 if a.network:childcfg['network']={'tap':'knc0','interface':'eth0','ip':'198.18.250.6/30','mac':'02:aa:00:00:00:02','hostname':'native-child'}
 if a.tapfd:
  childcfg['network'].pop('tap')
  childcfg['network']['tapfd']={'exec':[str(bin/'connector-ctl'),'tapfd','get','--mac','02:aa:00:00:00:02','--ip','198.18.250.6/30','knc0']}
 if a.fork:
  report['mode']='native-snapshot fork CLI'
  if a.reject_sockets:
   try:start('child',childcfg,parent='parent',output=cap)
   except RuntimeError:
    assert 'explicitly bound TCP listener needs rebind' in (work/'child.log').read_text()
   else:raise AssertionError('unsafe networked fork unexpectedly became Ready')
   assert json.loads(py('parent',"print(open('/tmp/progress.json').read())"))['counter']>before['counter']
   stop('child');stop('parent')
   assert not list(run.iterdir())
   report.update(passed=True,inherited_sockets_rejected=True,parent_continued=True,child_never_ready=True)
   print(json.dumps(report,indent=2));sys.exit(0)
  t=time.monotonic();start('child',childcfg,parent='parent',output=cap);report['fork_ready_ms']=(time.monotonic()-t)*1000
 else:
  t=time.monotonic();capture=command([bin/'sandbox-ctl','snapshot','--sandbox-id','parent','--run-root',run,*(['--upload'] if a.remote else ['--output',cap]),'--resume','--json'],capture_output=True,text=True)
  report['capture_ms']=(time.monotonic()-t)*1000;report['capture']=json.loads(capture.stdout)
  (work/'capture.log').write_text(capture.stderr)
  t=time.monotonic();start('child',childcfg,report['capture']['snapshotRef'] if a.remote else str(cap/'parent.snapshot'));report['restore_ready_ms']=(time.monotonic()-t)*1000
 if a.network and not a.tapfd:command(['ip','link','set','knc0','up'])
 if a.tapfd:report['connector_tapfd_automatic_gate']=True
 assert json.loads(py('parent',"print(open('/tmp/progress.json').read())"))['counter']>before['counter']
 py('parent',"open('/root/fork-value','w').write('parent')")
 child=json.loads(py('child',"print(open('/tmp/progress.json').read())"))
 assert child['identity']==before['identity'] and child['pid']==before['pid'] and child['counter']>=before['counter'],(before,child)
 assert py('child',"print(open('/root/fork-value').read())")=='before'
 py('child',"open('/root/fork-value','w').write('child')")
 assert py('parent',"print(open('/root/fork-value').read())")=='parent'
 if a.network:
  for sid,ip,mac,host in [('parent','198.18.250.2','02:aa:00:00:00:01','198.18.250.1'),('child','198.18.250.6','02:aa:00:00:00:02','198.18.250.5')]:
   identity=json.loads(py(sid,"import json,socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('"+host+"',9)); print(json.dumps([s.getsockname()[0],open('/sys/class/net/eth0/address').read().strip(),socket.gethostname()]))"))
   assert identity==[ip,mac,'native-'+sid],identity
   with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as listener:
    listener.bind((host,0));listener.settimeout(3);port=listener.getsockname()[1]
    token=uuid.uuid4().hex
    py(sid,"import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.sendto(b'"+token+"',('"+host+"',"+str(port)+"))")
    data,peer=listener.recvfrom(1024);assert data.decode()==token and peer[0]==ip,(data,peer)
  report['distinct_mac_ip_hostname_and_connections']=True
 if a.tcp_state:
  deadline=time.monotonic()+10
  while True:
   parent_state=json.loads(py('parent',"print(open('/tmp/progress.json').read())"))
   child_state=json.loads(py('child',"print(open('/tmp/progress.json').read())"))
   if child_state.get('peer_token') and child_state['peer_token']!=before['peer_token']:break
   assert time.monotonic()<deadline,(parent_state,child_state)
   time.sleep(.02)
  assert parent_state['peer_token']==before['peer_token'],(before,parent_state)
  assert len([v for v in tcp_connections if v[1]=='198.18.250.2'])==1,tcp_connections
  assert any(v[1]=='198.18.250.6' and v[0]==child_state['peer_token'] for v in tcp_connections),tcp_connections
  assert parent_state['random']!=child_state['random']
  assert parent_state['listener_port']==child_state['listener_port']
  for ip,state in [('198.18.250.2',parent_state),('198.18.250.6',child_state)]:
   with socket.create_connection((ip,state['listener_port']),timeout=3):pass
  for sid,ip,state in [('parent','198.18.250.2',parent_state),('child','198.18.250.6',child_state)]:
   token=uuid.uuid4().hex
   with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:sender.sendto(token.encode(),(ip,state['udp_port']))
   deadline=time.monotonic()+5
   while True:
    observed=json.loads(py(sid,"print(open('/tmp/progress.json').read())"))
    if observed['udp_token']==token:break
    assert time.monotonic()<deadline,observed
    time.sleep(.02)
   other='parent' if sid=='child' else 'child'
   assert json.loads(py(other,"print(open('/tmp/progress.json').read())"))['udp_token']!=token
  report['wildcard_udp_independent']=True
  report.update(parent_tcp_uninterrupted=True,child_tcp_reconnected=True,wildcard_listener_preserved=True,distinct_guest_random=True)
 first,last=('child','parent') if a.child_first else ('parent','child')
 previous=json.loads(py(last,"print(open('/tmp/progress.json').read())"))
 stop(first)
 assert py(last,"print(open('/root/fork-value').read())")==last
 later=json.loads(py(last,"print(open('/tmp/progress.json').read())"));assert later['counter']>previous['counter']
 stop(last);assert not list(run.iterdir()),list(run.iterdir())
 report['guest_loopback_preserved']=bool(a.tcp_state)
 report.update(passed=True,process_state_inherited=True,parent_continued=True,independent_writes=True,survivor_after_first_delete=last,independent_destroy=True)

finally:
 for sid in reversed(list(processes)):stop(sid)
 if tcp_server:tcp_server.shutdown();tcp_server.server_close()
 for tap in reversed(taps):command(['ip','link','del',tap])
 (work/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 if not list(run.iterdir()):run.rmdir()
print(json.dumps(report,indent=2))
