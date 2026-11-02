import os,json,time,sys,uuid,subprocess,base64,re,traceback
from pathlib import Path
import httpx
from extent_accounting import scan
product,output,config_path=sys.argv[1:];out=Path(output)/product;out.mkdir()
cfg=json.loads(Path(config_path).read_text())
c=json.loads(Path(cfg['products'][product]['access']).read_text());os.environ.update(E2B_API_KEY=c['api_key'],E2B_DOMAIN=c['domain'],SSL_CERT_FILE=c['ca_file'],NO_PROXY='*')
if product=='cube':os.environ['E2B_API_URL']=c['api_url']
from e2b import Sandbox
s=None;instances=[];marker=' # history-'+uuid.uuid4().hex;hosts=Path('/etc/hosts');r={'product':product,'versions':[],'measurements':{}}
def save(): (out/'results.json').write_text(json.dumps(r,indent=2))
def register(x):
 instances.append(x)
 if product=='kuasar':
  with hosts.open('a') as f:f.write('\n127.0.0.2 '+x.get_host(49983)+marker+'\n')
def measure(label):
 subprocess.run(['sync','-f',cfg['mount']],check=True);a=[]
 for _ in range(3):
  f=os.statvfs(cfg['mount']);a.append((f.f_blocks-f.f_bfree)*f.f_frsize);time.sleep(.5)
 dirs={}
 for name in ('kuasar/store','kuasar/cache-rocks','kuasar/runs','cubesandbox','cubesandbox-extra','cubesandbox-support'):
  q=subprocess.run(['du','-s','-B1',str(Path(cfg['mount'])/name)],capture_output=True,text=True)
  if q.returncode==0:dirs[name]=int(q.stdout.split()[0])
 # Count physical data extents once, excluding the other product and RocksDB cache.
 paths=cfg['products'][product]['extent_paths']
 first=scan(paths);time.sleep(1);second=scan(paths)
 r['measurements'][label]={'xfs_used_samples':a,'directory_allocated_bytes':dirs,'extent_samples':[first,second]};save()
try:
 case=json.loads((Path(output)/'case.json').read_text());r['case']=case
 measure('baseline')
 for v in range(case.get('instances',3)):
  s=Sandbox.create(c['template_id'],timeout=1800);register(s);r['source_sid']=s.sandbox_id
  assert s.commands.run('printf READY').exit_code==0
  if product=='kuasar':
   os.environ['LD_LIBRARY_PATH']=str(Path(c['bin']).parent/'lib')
   for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
     if s.sandbox_id.encode() not in (p/'cmdline').read_bytes():continue
     env=dict(x.split(b'=',1) for x in (p/'environ').read_bytes().split(b'\0') if b'=' in x)
     if b'MANIFEST_KEY' in env:os.environ['MANIFEST_KEY']=env[b'MANIFEST_KEY'].decode()
    except OSError:pass
   assert 'MANIFEST_KEY' in os.environ
  seed=case['seed']+(v if case['mode']=='different' else 0)
  init=f"import random,os;f=open('/home/user/history.bin','wb');f.write(random.Random({seed}).randbytes(64*1024*1024));f.flush();os.fsync(f.fileno());f.close()"
  import shlex
  q=s.commands.run('python3 -c '+shlex.quote(init));assert q.exit_code==0
  memory_code="""import random,hashlib,json,uuid,zlib
from http.server import BaseHTTPRequestHandler,HTTPServer
b=bytearray(256*1024*1024)
rng=random.Random(SEED)
if HIGH:
    for offset in range(0,len(b),1024*1024):
        b[offset:offset+1024*1024]=rng.randbytes(1024*1024)
else:
    pattern=rng.randbytes(256)*16
    for offset in range(0,len(b),4096):b[offset:offset+4096]=pattern
instance=str(uuid.uuid4())
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        from urllib.parse import urlparse,parse_qs
        seed=int(parse_qs(urlparse(self.path).query)['seed'][0])
        # Dirty every 4-KiB page with a nonzero XOR; equal snapshots then diverge.
        for offset in range(0,len(b),4096):
            b[offset]^=((seed+offset//4096)%255)+1
        self.do_GET()
    def do_GET(self):
        result=dict(instance=instance,sha256=hashlib.sha256(b).hexdigest(),size=len(b),sample_zlib_ratio=len(zlib.compress(b[:1024*1024]))/(1024*1024))
        data=json.dumps(result).encode()
        self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def log_message(self,*args):pass
HTTPServer(('127.0.0.1',8002),Handler).serve_forever()
""".replace('SEED',str(seed+100)).replace('HIGH',str(case['entropy']=='high'))
  s.files.write('/home/user/history-memory.py',memory_code)
  s.commands.run('python3 /home/user/history-memory.py',background=True)
  probe="python3 -c 'import urllib.request;print(urllib.request.urlopen(\"http://127.0.0.1:8002/\").read().decode())'"
  deadline=time.monotonic()+30
  while True:
   try:
    q=s.commands.run(probe)
    if q.exit_code==0:break
   except Exception:
    if time.monotonic()>deadline:raise
   if time.monotonic()>deadline:raise RuntimeError('Memory workload did not become ready')
   time.sleep(.2)
  r['memory_baseline']=json.loads(q.stdout)
  digest=s.commands.run('sha256sum /home/user/history.bin').stdout.split()[0]
  if product=='cube':
   with httpx.Client(trust_env=False,timeout=240) as client:
    q=client.post(c['api_url']+'/sandboxes/'+s.sandbox_id+'/snapshots',headers={'X-API-KEY':c['api_key']},json={'name':'comparison-history-'+str(v),'backend':'xfs'});q.raise_for_status();ref=q.json()['snapshotID']
   template=ref
  else:
   d=out/('v'+str(v));d.mkdir();binary=str(Path(c['bin'])/'sandbox-ctl')
   q=subprocess.run([binary,'snapshot','--sandbox-id',s.sandbox_id,'--run-root',c['run_root']+'/sandboxes','--output',str(d),'--resume'],text=True,capture_output=True,timeout=180);(d/'snapshot.log').write_text(q.stdout+q.stderr);assert q.returncode==0,q.stderr
   paths=list({p.resolve() for p in d.glob('*.snapshot')});assert len(paths)==1
   q=subprocess.run([binary,'publish','--manifest-config',c['work_dir']+'/manifest.yaml',str(paths[0])],text=True,capture_output=True,timeout=300);(d/'publish.log').write_text(q.stdout+q.stderr);assert q.returncode==0,q.stderr
   ref=re.findall(r'manifest://[0-9a-f]{64}',q.stdout)[-1];template='e2b-snp-'+base64.b64encode(ref.encode()).decode().rstrip('=')
  r['versions'].append({'version':v,'source_sid':s.sandbox_id,'ref':ref,'template':template,'sha256':digest,'memory_baseline':r['memory_baseline']})
  # Published artifacts must restore without temporary local exports.
  if product=='kuasar':
   r['removed_staging_bytes']=0
   for d in [out/('v'+str(v))]:
    for p in d.iterdir():
     if p.suffix not in ('.snapshot','.sandbox'):continue
     assert p.resolve().is_relative_to(out.resolve())
     if not p.is_symlink():r['removed_staging_bytes']+=p.stat().st_blocks*512
     p.unlink()
  # Delete original before restoring historical snapshots: verify independence.
  s.kill();instances.remove(s);time.sleep(3);measure('retained_'+str(v+1));print(product,'retained',v+1,flush=True)
 for v in r['versions']:
  x=Sandbox.create(v['template'],timeout=300);register(x)
  q=x.commands.run('sha256sum /home/user/history.bin');assert q.exit_code==0 and q.stdout.split()[0]==v['sha256']
  q=x.commands.run(probe);assert q.exit_code==0
  observed=json.loads(q.stdout);assert observed==v['memory_baseline'];v['memory_verified']=True
  v['restore_verified']=True;x.kill();instances.remove(x);save()
 r['success']=True
except Exception:r['success']=False;r['error']=traceback.format_exc();print(r['error'],flush=True)
finally:
 r['delete_errors']=[]
 for x in instances:
  try:x.kill()
  except Exception as e:r['delete_errors'].append(str(e))
 if product=='kuasar':hosts.write_text(''.join(l for l in hosts.read_text().splitlines(True) if marker not in l))
 save()
if not r['success']:sys.exit(1)
