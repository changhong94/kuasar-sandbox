"""Run INSIDE the isolated Linux host, never reboot or kill the physical 113 host."""
from pathlib import Path
import os,json,sys,time,uuid,shlex,urllib.request
F=Path('/home/hong/src/research/python-latest-113');P=F/'deploy/fork';R=F/'reboot-tests';R.mkdir(exist_ok=True)
os.environ.update(E2B_API_KEY=(P/'api-key').read_text().strip(),E2B_API_URL='http://127.0.0.1:18887',E2B_SANDBOX_URL='http://127.0.0.1:18887',NO_PROXY='*',no_proxy='*')
from e2b import Sandbox
program="""import os,secrets,json,sqlite3
secret=secrets.token_hex(24)
counter=0
db=sqlite3.connect('/tmp/reboot.sqlite3')
db.execute('PRAGMA journal_mode=WAL')
db.execute('PRAGMA synchronous=FULL')
db.execute('CREATE TABLE state (id INTEGER PRIMARY KEY, value INTEGER NOT NULL)')
db.execute('INSERT INTO state VALUES (1,0)')
db.commit()
os.mkfifo('/tmp/reboot-fifo')
while True:
 with open('/tmp/reboot-fifo') as f: nonce=f.read().strip()
 counter+=1
 db.execute('UPDATE state SET value=value+1 WHERE id=1')
 db.commit()
 assert db.execute('SELECT value FROM state WHERE id=1').fetchone()[0]==counter
 with open('/tmp/reboot-response','w') as f:json.dump(dict(secret=secret,nonce=nonce,counter=counter,pid=os.getpid()),f)
"""
def cmd(s,c):
 r=s.commands.run(c,user='root',timeout=60);assert r.exit_code==0,(c,r.stderr);return r.stdout.strip()
def challenge(s):
 nonce=uuid.uuid4().hex;cmd(s,'printf %s '+nonce+' > /tmp/reboot-fifo')
 for _ in range(100):
  value=cmd(s,'cat /tmp/reboot-response 2>/dev/null || true')
  if value:
   try:
    result=json.loads(value)
    if result['nonce']==nonce:cmd(s,'rm /tmp/reboot-response');return result
   except json.JSONDecodeError:pass
  time.sleep(.01)
 raise RuntimeError('restored process did not answer')
def write(s,value):
 code="import os; f=open('/tmp/reboot-file','w');f.write("+repr(value)+");f.flush();os.fsync(f.fileno());f.close();d=os.open('/tmp',os.O_DIRECTORY);os.fsync(d);os.close(d)"
 cmd(s,'python3 -c '+shlex.quote(code))
def save(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2))
 with tmp.open('rb') as f:os.fsync(f.fileno())
 tmp.replace(path);fd=os.open(path.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
phase=sys.argv[1];run=sys.argv[2];path=R/(run+'.json')
if phase=='prepare':
 assert not path.exists();d={'before_boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'sandboxes':[]};save(path,d)
 parent=Sandbox.create('base',timeout=3600,request_timeout=300);d['sandboxes'].append({'id':parent.sandbox_id});save(path,d)
 cmd(parent,'printf %s '+shlex.quote(program)+' > /tmp/reboot-process.py');pid=int(cmd(parent,'nohup /usr/local/bin/python3 /tmp/reboot-process.py > /tmp/reboot-log 2>&1 < /dev/null & echo $!'))
 for _ in range(100):
  if cmd(parent,'test -p /tmp/reboot-fifo && echo yes || true')=='yes':break
  time.sleep(.01)
 first=challenge(parent);assert first['pid']==pid
 req=urllib.request.Request(os.environ['E2B_API_URL']+'/sandboxes/'+parent.sandbox_id+'/fork',data=b'{"timeout":3600}',headers={'X-API-Key':os.environ['E2B_API_KEY'],'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=300) as f:sid=json.load(f)[0]['sandbox']['sandboxID']
 child=Sandbox.connect(sid,timeout=3600,request_timeout=300);d['sandboxes'].append({'id':sid});save(path,d)
 for s,row in zip([parent,child],d['sandboxes']):
  row['file']=uuid.uuid4().hex;write(s,row['file']);row['memory']=challenge(s);assert row['memory']['secret']==first['secret'];s.pause(request_timeout=300);assert not s.is_running();row['paused']=True;save(path,d)
 d['ready_for_host_reboot']=True;save(path,d);print('CHECKPOINTS_DURABLE',run,flush=True)
elif phase=='verify':
 d=json.loads(path.read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot!=d['before_boot'];d['after_boot']=boot
 clients=[]
 for row in d['sandboxes']:
  s=Sandbox.connect(row['id'],timeout=3600,request_timeout=300);clients.append(s)
  answer=challenge(s);assert answer['pid']==row['memory']['pid'];assert answer['secret']==row['memory']['secret'];assert answer['counter']==row['memory']['counter']+1
  assert s.files.read('/tmp/reboot-file')==row['file']
  check="import sqlite3,json; c=sqlite3.connect('/tmp/reboot.sqlite3'); print(json.dumps([c.execute('PRAGMA integrity_check').fetchone()[0],c.execute('SELECT value FROM state WHERE id=1').fetchone()[0]]))"
  row['sqlite_after_restore']=json.loads(cmd(s,'python3 -c '+shlex.quote(check)))
  assert row['sqlite_after_restore']==['ok',answer['counter']]
  row['after_memory']=answer;row['file_verified']=True;save(path,d)
 # Verify post-restore writes remain independent, then restore expected values.
 write(clients[0],'parent-after-reboot')
 assert clients[1].files.read('/tmp/reboot-file')==d['sandboxes'][1]['file']
 write(clients[1],'child-after-reboot')
 assert clients[0].files.read('/tmp/reboot-file')=='parent-after-reboot'
 for s,row in zip(clients,d['sandboxes']):write(s,row['file'])
 d['post_restore_independent_writes']=True;save(path,d)
 if run.endswith('2'):
  req=urllib.request.Request(os.environ['E2B_API_URL']+'/sandboxes/'+clients[0].sandbox_id+'/fork',data=b'{"timeout":3600}',headers={'X-API-Key':os.environ['E2B_API_KEY'],'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=300) as f:gid=json.load(f)[0]['sandbox']['sandboxID']
  d['grandchild_id']=gid;save(path,d)
  g=Sandbox.connect(gid,timeout=3600,request_timeout=300)
  assert challenge(g)['secret']==d['sandboxes'][0]['memory']['secret']
  write(g,'grandchild-private');assert clients[0].files.read('/tmp/reboot-file')==d['sandboxes'][0]['file']
  g.kill();d['fork_after_reboot_and_destroy']=True;save(path,d)
 if run.endswith('3'):
  import signal
  sys.path.insert(0,str(F/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'));import vm_rpc
  info=vm_rpc.admin(P/'admin.sock','sandbox-get',sandbox_id=clients[1].sandbox_id)
  pid=info['live_fork']['pid'];assert info['live_fork']['api_socket'].encode() in Path(f'/proc/{pid}/cmdline').read_bytes()
  assert pid!=vm_rpc.admin(P/'admin.sock','sandbox-get',sandbox_id=clients[0].sandbox_id)['live_fork']['pid']
  fd=os.pidfd_open(pid);signal.pidfd_send_signal(fd,signal.SIGKILL);os.close(fd)
  for _ in range(100):
   if vm_rpc.admin(P/'admin.sock','sandbox-get',sandbox_id=clients[1].sandbox_id)['status']=='stopped':break
   time.sleep(.05)
  else:raise AssertionError('restored VMM exit did not reach lifecycle monitor')
  d['restored_controller_exit_monitored']=True;save(path,d)
 order=[0,1] if run.endswith('1') else [1,0];clients[order[0]].kill();d['sandboxes'][order[0]]['destroyed']=True;save(path,d)
 survivor=clients[order[1]];row=d['sandboxes'][order[1]];assert challenge(survivor)['secret']==row['memory']['secret'];assert survivor.files.read('/tmp/reboot-file')==row['file'];write(survivor,'survived-other-destroy');assert survivor.files.read('/tmp/reboot-file')=='survived-other-destroy';survivor.kill();row['destroyed']=True;d['success']=True;d['destroy_order']=order;save(path,d);print(json.dumps(d,indent=2))
else:raise ValueError(phase)
