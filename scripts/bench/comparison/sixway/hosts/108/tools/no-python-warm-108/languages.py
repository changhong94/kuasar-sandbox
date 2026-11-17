import os,sys,json,time,uuid,shlex,statistics,urllib.request,concurrent.futures as cf
from pathlib import Path
M=Path('/opt/bench108');R=M/'results/no-python-warm-108';Q=M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b';sys.path.insert(0,str(Q));import vm_rpc
url='http://127.0.0.1:18887';key=(M/'deploy/fork/api-key').read_text().strip();os.environ.update(E2B_API_KEY=key,E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
from e2b import Sandbox

def req(path,body=None):
 return json.load(urllib.request.urlopen(urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers={'X-API-Key':key,'Content-Type':'application/json'}),timeout=180))
def run(s,c):
 r=s.commands.run(c,user='root',timeout=60);assert r.exit_code==0,(r.stderr,r.stdout);return r.stdout.strip()
from slot_disk import SlotDisks
cache_started=time.perf_counter_ns()
SlotDisks(M/'data/fork/slot-disks',json.loads((M/'deploy/fork/images.json').read_text()))
(R/'language-disk-cache-preparation.json').write_text(json.dumps({'elapsed_ms':(time.perf_counter_ns()-cache_started)/1e6}))
print(json.dumps(req('/images/reload',{})),flush=True)
catalog=json.loads((M/'deploy/fork/images.json').read_text());prep={}
for name,binary in [('node','/usr/local/bin/node'),('ruby','/usr/local/bin/ruby')]:
 t=time.perf_counter_ns();s=Sandbox.create(name,timeout=300)
 try:
  info=vm_rpc.admin(M/'deploy/fork/admin.sock','sandbox-get',sandbox_id=s.sandbox_id)['live_fork']
  z=vm_rpc.execute(info['vsock_socket'],['/bin/busybox','sh','-c','/bin/busybox cat > /run/residency; /bin/busybox chmod 700 /run/residency'],(M/'tools/no-python-warm-108/residency').read_bytes());assert z['exit_code']==0
  z=vm_rpc.execute(info['vsock_socket'],['/run/residency','/run/image-root'+binary]);assert z['exit_code']==0
  assert int(z['stdout'].decode().split()[1])==0,z
  z2=vm_rpc.execute(info['vsock_socket'],['/bin/busybox','sh','-c','for f in /proc/[0-9]*/comm; do /bin/busybox cat "$f" 2>/dev/null; done']);assert z2['exit_code']==0
  assert name not in z2['stdout'].decode().splitlines()
  prep[name]={'first_create_and_audit_ms':(time.perf_counter_ns()-t)/1e6,'binary_residency':z['stdout'].decode(),'no_interpreter_process':True,'manifest':catalog[name]['manifest'],'startup_read_files':catalog[name].get('startup_read_files',[])}
 finally:s.kill()
(R/'language-preparation.json').write_text(json.dumps(prep,indent=2))
rows=[]
def sample(name,i):
 marker='READY_'+uuid.uuid4().hex
 argv=['exec','/usr/local/bin/node','-e','console.log(process.argv[1])',marker] if name=='node' else ['exec','/usr/local/bin/ruby','-e','$stdout.sync = true; puts ARGV[0]',marker]
 cmd=shlex.join(argv);chunks=[];received=None;s=None;row=dict(language=name,index=i,command=cmd,marker=marker,manifest=catalog[name]['manifest'])
 def cb(chunk):
  nonlocal received
  chunks.append(chunk)
  if received is None and marker+'\n' in ''.join(chunks):received=time.perf_counter_ns()
 start=time.perf_counter_ns()
 try:
  s=Sandbox.create(name,timeout=300);r=s.commands.run(cmd,user='root',timeout=60,on_stdout=cb)
  assert r.exit_code==0 and r.stdout.strip()==marker and received is not None,(r.stderr,r.stdout)
  row.update(ready_ms=(received-start)/1e6,start_ns=start,received_ns=received,success=True,sandbox_id=s.sandbox_id)
 finally:
  if s is not None:s.kill();row['destroyed']=True
  (R/f'{name}-{i:02d}.json').write_text(json.dumps(row,indent=2))
 return row
with cf.ThreadPoolExecutor(2) as pool:
 for r in range(5):
  for name in (['node','ruby'] if r%2==0 else ['ruby','node']):
   rows.extend(pool.map(lambda i:sample(name,i),[2*r+1,2*r+2]));time.sleep(2)
summary={name:dict(n=10,median_ms=statistics.median(x['ready_ms'] for x in rows if x['language']==name),max_ms=max(x['ready_ms'] for x in rows if x['language']==name)) for name in ['node','ruby']}
(R/'languages-summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
checks={}
for name in ['node','ruby']:
 p=Sandbox.create(name,timeout=180);c=None
 try:
  run(p,'echo inherited > /tmp/fork-proof')
  desc=req('/sandboxes/'+p.sandbox_id+'/fork',{'timeout':180})[0]['sandbox'];c=Sandbox.connect(desc['sandboxID'])
  assert run(c,'cat /tmp/fork-proof')=='inherited'
  run(p,'echo parent > /tmp/fork-proof');run(c,'echo child > /tmp/fork-proof')
  assert run(p,'cat /tmp/fork-proof')=='parent' and run(c,'cat /tmp/fork-proof')=='child'
  p.kill();p=None;assert run(c,'cat /tmp/fork-proof')=='child'
  checks[name]={'independent_writes':True,'child_survives_parent_destroy':True}
 finally:
  if c:c.kill()
  if p:p.kill()
(R/'languages-isolation.json').write_text(json.dumps(checks,indent=2))
