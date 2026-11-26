import resource_worker181 as a
from extent_accounting import scan
from pathlib import Path
import json,time,shlex,hashlib
R=a.R/'measurements/storage'/a.product;R.mkdir(parents=True,exist_ok=True)
def measure():
 d=scan(a.paths[a.product]);d.update(a.resources());return d
for i in range(3):
 for kind in ('same','different'):
  out=R/f'{i}-{kind}.json'
  if out.exists():
   d=json.load(open(out))
   if d.get('success') and not d.get('owned_remaining'):continue
   raise RuntimeError('Failed sample requires cleanup review: '+str(out))
  a.wait(a.c);row={'iteration':i,'content':kind,'product':a.product,'image_digest':a.cfg['_languages']['python']['digest'],'paths':a.paths[a.product],'baseline':measure()};sandboxes=[];digests=[]
  try:
   for j in range(2):
    s=a.create();sandboxes.append(s);a.b.save(out.with_suffix('.ledger'),[a.b.sid(x)for x in sandboxes])
    seed=j if kind=='different'else 0
    code="""import hashlib,os
h=hashlib.sha256()
with open('/tmp/fiveway.bin','wb') as f:
 for k in range(32):
  b=hashlib.shake_256(('fiveway-storage-%d-'%SEED+str(k)).encode()).digest(1048576);h.update(b);f.write(b)
 f.flush();os.fsync(f.fileno())
print(h.hexdigest())""".replace('SEED',str(seed))
    expected=hashlib.sha256()
    for k in range(32):expected.update(hashlib.shake_256(('fiveway-storage-%d-'%seed+str(k)).encode()).digest(1048576))
    assert a.cmd(s,'python3 -c '+shlex.quote(code))==expected.hexdigest()
    digests.append(expected.hexdigest())
   row['running']=measure()
   for s in sandboxes:a.pause(s)
   row['paused']=measure()
   sandboxes=[a.resume(s)for s in sandboxes]
   for s,d in zip(sandboxes,digests):assert a.cmd(s,'sha256sum /tmp/fiveway.bin').split()[0]==d
   n=i%2;a.b.kill(sandboxes[n]);sandboxes.pop(n)
   assert a.cmd(sandboxes[0],'sha256sum /tmp/fiveway.bin').split()[0]==digests[1-n]
   row.update(success=True,restore_verified=True,independent_delete_verified=True)
  except BaseException as e:row.update(success=False,error=repr(e));raise
  finally:
   for s in list(sandboxes):
    try:a.b.kill(s);sandboxes.remove(s)
    except Exception as e:row['cleanup_error']=repr(e)
   row['owned_remaining']=[a.b.sid(s)for s in sandboxes];a.b.save(out.with_suffix('.ledger'),row['owned_remaining'])
   if not sandboxes:a.wait(a.c);time.sleep(2);row['settled']=measure()
   a.b.save(out,row)
  print(a.product,i,kind,'OK',flush=True)
