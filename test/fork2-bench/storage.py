#!/usr/bin/env python3
"""Two independent persistent sandboxes; FIEMAP union on isolated fork2 XFS."""
import json,pathlib,os,time,statistics,shlex,argparse,urllib.request,subprocess,sqlite3,re,hashlib
from e2b import Sandbox
from extent_accounting import scan
os.environ.update(NO_PROXY='*',no_proxy='*')
p=argparse.ArgumentParser();p.add_argument('--count',type=int,default=10);p.add_argument('--output',required=True);a=p.parse_args()
c=json.loads(pathlib.Path('/srv/fork2/console.json').read_text());im=json.loads(pathlib.Path('/srv/fork2/data/registry/python.json').read_text());opts=dict(api_key=c['key'],api_url=c['api'],sandbox_url='http://127.0.0.1:19211')
def settled():
 end=time.monotonic()+60
 while time.monotonic()<end:
  with sqlite3.connect('file:/home/hong/src/research/fork2-control-persistent/node-ctl.db?mode=ro',uri=True) as db:
   ids={r[0] for r in db.execute('select p.run_id from prepared_vm_leases p join run_pool_ownership o on p.run_id=o.run_id')}
   owned={r[0] for r in db.execute('select run_id from run_pool_ownership')}
  expected=sum(p['size'] for p in json.loads(pathlib.Path('/srv/fork2/conductor.json').read_text())['units']['runner_pools'])
  units=subprocess.check_output(['systemctl','list-units','fork2-runner@*.service','--state=running','--plain','--no-legend','--no-pager'],text=True)
  active={x.split('@')[1].split('.service')[0] for x in units.splitlines() if '@' in x}
  if len(ids)==64 and len(owned)==expected and active==owned:return
  time.sleep(.02)
 raise TimeoutError('fork2 did not return to its configured idle runners')
def measure():
 data=scan(['/srv/fork2/data','/home/hong/src/research/fork2-control-persistent'])
 fs=os.statvfs('/srv/fork2/data');data['dedicated_filesystem_used_bytes']=(fs.f_blocks-fs.f_bfree)*fs.f_frsize
 pss=0;fds=0;processes=[]
 for d in pathlib.Path('/proc').glob('[0-9]*'):
  try:
   if '/fork2-' not in (d/'cgroup').read_text():continue
   text=(d/'smaps_rollup').read_text();pss+=int(re.search(r'^Pss:\s+(\d+)',text,re.M)[1]);fds+=len(list((d/'fd').iterdir()));processes.append(int(d.name))
  except (OSError,ValueError,TypeError):pass
 data.update(product_pss_kib=pss,product_fds=fds,processes=processes);return data
rows=[]
for i in range(a.count):
 for kind in ('same','different'):
  sandboxes=[];digests=[];row={'iteration':i,'content':kind};settled();row['baseline']=measure()
  try:
   for j in range(2):
    s=Sandbox.create(template=im['template_id'],timeout=600,**opts);sandboxes.append(s)
    mount_result=s.commands.run('cat /proc/mounts',user='root',cwd='/',timeout=120);assert mount_result.exit_code==0
    row.setdefault('guest_mounts',[]).append(mount_result.stdout)
    # Same as the retained-storage workload: 32 MiB deterministic content,
    # distinct seed in the different-content case, explicit fsync included.
    seed=j if kind=='different' else 0
    code="""import hashlib,os
h=hashlib.sha256()
with open('/tmp/fiveway.bin','wb') as f:
 for k in range(32):
  b=hashlib.shake_256(('fiveway-storage-%d-'%SEED+str(k)).encode()).digest(1048576);h.update(b);f.write(b)
 f.flush();os.fsync(f.fileno())
print(h.hexdigest())""".replace('SEED',str(seed))
    expected=hashlib.sha256()
    for k in range(32):expected.update(hashlib.shake_256(('fiveway-storage-%d-'%seed+str(k)).encode()).digest(1048576))
    r=s.commands.run('/usr/local/bin/python3 -c '+shlex.quote(code),user='root',cwd='/',timeout=120)
    assert r.exit_code==0 and r.stdout.strip()==expected.hexdigest()
    digests.append(expected.hexdigest())
   assert (digests[0]!=digests[1])==(kind=='different')
   row['running']=measure()
   for s in sandboxes:
    req=urllib.request.Request(c['api']+'/sandboxes/'+s.sandbox_id+'/pause',data=b'{"memory":true}',headers={'X-API-Key':c['key'],'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=120) as f:f.read()
   time.sleep(1);row['paused']=measure()
   for s,digest in zip(sandboxes,digests):
    restored=Sandbox.connect(s.sandbox_id,timeout=600,**opts)
    r=restored.commands.run('sha256sum /tmp/fiveway.bin',user='root',cwd='/',timeout=120)
    assert r.exit_code==0 and r.stdout.split()[0]==digest
   row['restore_digests_verified']=True
   deleted_index=i%2;survivor_index=1-deleted_index
   sandboxes[deleted_index].kill()
   sandboxes.pop(deleted_index)
   survivor=sandboxes[0]
   r=survivor.commands.run('sha256sum /tmp/fiveway.bin',user='root',cwd='/',timeout=120)
   assert r.exit_code==0 and r.stdout.split()[0]==digests[survivor_index]
   row['independent_delete_verified']=True;row['first_deleted_index']=deleted_index
   sandboxes=[survivor]
  finally:
   for s in reversed(sandboxes):s.kill()
   settled();time.sleep(2);row['settled']=measure()
  row['all_test_sandboxes_destroyed']=True;rows.append(row)
  pathlib.Path(a.output).write_text(json.dumps({'image_digest':im['manifest'],'scope':'FIEMAP physical extent union of /srv/fork2/data, including images and pool; PSS only fork2 service cgroups; delta from immediately preceding full idle 64-slot pool baseline; includes /srv/fork2/data and persistent control DB','samples':rows},indent=2));print(json.dumps({k:row[k] for k in ('iteration','content','all_test_sandboxes_destroyed')}),flush=True)
for kind in ('same','different'):
 for phase in ('running','paused','settled'):
  values=[(r[phase]['unique_extent_bytes']-r['baseline']['unique_extent_bytes'])/(1<<20) for r in rows if r['content']==kind]
  print(kind,phase,'unique_extent_delta_MiB',statistics.median(values),max(values),flush=True)
