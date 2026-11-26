import os
import os,sys,json,time,pathlib,subprocess,sqlite3,urllib.request,re,statistics,uuid,shlex,threading,concurrent.futures as cf,fcntl,traceback
os.environ.update(NO_PROXY='*',no_proxy='*')
from e2b import Sandbox
R=pathlib.Path('/home/hong/src/research/sevenway-current-20261126/fork2');OUT=R/'results'
def save(p,v):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(v,indent=2));q.replace(p)
def resources(product):
 start=time.monotonic_ns();pattern=(r'/fork2-(?:runner@|shared-controller\.|conductor\.|proxy\.|switch\.|store\.)' if product=='fork2' else r'/fork2-old-print-(?:compare|store)\.service');detail={};roots=set();races=[];kernel_threads=[]
 for p in pathlib.Path('/proc').glob('[0-9]*'):
  matched=False
  try:
   cg=(p/'cgroup').read_text()
   if not re.search(pattern,cg):continue
   matched=True
   cpath=cg.split('::',1)[1].strip();parts=cpath.strip('/').split('/');end=next(i for i,v in enumerate(parts) if v.endswith('.service'));roots.add('/'+'/'.join(parts[:end+1]));vals={}
   stat=(p/'stat').read_text().rsplit(')',1)[1].split();identity=stat[19]
   if int(stat[6]) & 0x00200000:
    kernel_threads.append({'pid':p.name,'comm':(p/'comm').read_text().strip()});continue
   for l in (p/'smaps_rollup').read_text().splitlines():
    a=l.split()
    if len(a)>=3 and a[2]=='kB':vals[a[0].rstrip(':')]=int(a[1])
   assert identity==(p/'stat').read_text().rsplit(')',1)[1].split()[19]
   detail[p.name]={'comm':(p/'comm').read_text().strip(),'start_ticks':identity,'cgroup':cpath,'pss_kib':vals['Pss'],'private_kib':vals.get('Private_Clean',0)+vals.get('Private_Dirty',0),'pss_anon_kib':vals.get('Pss_Anon',0),'pss_file_kib':vals.get('Pss_File',0),'swap_pss_kib':vals.get('SwapPss',0),'locked_kib':vals.get('Locked',0)}
  except (OSError,ProcessLookupError,AssertionError):
   if matched:races.append(p.name)
 assert detail,(product,'no process')
 cgroups={}
 for root in sorted(roots):
  if any(root.startswith(other+'/') for other in roots):continue
  p=pathlib.Path('/sys/fs/cgroup')/root.lstrip('/')
  try:
   stats={k:int(v) for k,v in (l.split() for l in (p/'memory.stat').read_text().splitlines())};cgroups[root]={'current':int((p/'memory.current').read_text()),'anon':stats.get('anon',0),'file':stats.get('file',0),'kernel':stats.get('kernel',0),'swap':int((p/'memory.swap.current').read_text()) if (p/'memory.swap.current').exists() else 0}
  except OSError:races.append(root)
 return {'start_ns':start,'end_ns':time.monotonic_ns(),'pss_mib':sum(v['pss_kib'] for v in detail.values())/1024,'private_mib':sum(v['private_kib'] for v in detail.values())/1024,'pss_anon_mib':sum(v['pss_anon_kib'] for v in detail.values())/1024,'pss_file_mib':sum(v['pss_file_kib'] for v in detail.values())/1024,'locked_mib':sum(v['locked_kib'] for v in detail.values())/1024,'swap_pss_mib':sum(v['swap_pss_kib'] for v in detail.values())/1024,'cgroup_current_mib':sum(v['current'] for v in cgroups.values())/2**20,'cgroup_file_mib':sum(v['file'] for v in cgroups.values())/2**20,'cgroup_anon_mib':sum(v['anon'] for v in cgroups.values())/2**20,'processes':detail,'cgroups':cgroups,'races':races,'kernel_threads_without_userspace_pss':kernel_threads}
def worker(product):
 if product=='fork2':
  c=json.load(open('/srv/fork2/console.json'));opts=dict(api_key=c['key'],api_url=c['api'],sandbox_url='http://127.0.0.1:19211');template=json.load(open('/srv/fork2/data/registry/python.json'))['template_id']
 else:
  key=pathlib.Path('/home/hong/src/research/fork2-print-compare-113/old/deploy/api-key').read_text().strip();opts=dict(api_key=key,api_url='http://127.0.0.1:18887',sandbox_url='http://127.0.0.1:18887');template='base'
 owned=[];result={'product':product,'growth':[],'arrays':{},'owned':[]};path=OUT/(product+'.json')
 def persist():result['owned']=[s.sandbox_id for s in owned];save(path,result)
 def run(s,cmd,**kwargs):
  r=s.commands.run(cmd,user='root',cwd='/',timeout=120,**kwargs);assert r.exit_code==0,(s.sandbox_id,r.stderr);return r.stdout.strip()
 def gate():
  deadline=time.monotonic()+240
  while time.monotonic()<deadline:
   if product=='old':
    try:
     r=urllib.request.Request(opts['api_url']+'/template-pool',headers={'X-API-Key':opts['api_key']});v=json.load(urllib.request.urlopen(r,timeout=5));ok=v['ready']==64 and v['preparing']==0 and v.get('binding',0)==0
    except Exception:ok=False
   else:
    with sqlite3.connect('file:/home/hong/src/research/fork2-control-persistent/node-ctl.db?mode=ro',uri=True) as db:
     ids=[x[0] for x in db.execute('select run_id from prepared_vm_leases')];ok=len(ids)==64 and db.execute('select count(*) from sandboxes').fetchone()[0]==len(owned)
    if ok:
     pressure=json.loads(subprocess.check_output(['curl','-sf','--max-time','3','--unix-socket','/run/fork2/node.sock','http://localhost/internal/admin/resource-pressure']))
     ok=any(p.get('name')=='prepared' and p.get('states',{}).get('idle')==64 and p.get('states',{}).get('starting',0)==0 and p.get('states',{}).get('bound',0)==len(owned) for p in pressure['runner_pools'])
   if ok:return
   time.sleep(.2)
  raise TimeoutError(('pool',product,len(owned)))
 def sample():
  rows=[]
  for _ in range(5):rows.append(resources(product));time.sleep(1)
  assert not any(v['races'] for v in rows),[v['races'] for v in rows]
  return {'median':{k:statistics.median(v[k] for v in rows) for k in ['pss_mib','locked_mib','private_mib','pss_anon_mib','pss_file_mib','swap_pss_mib','cgroup_current_mib','cgroup_file_mib','cgroup_anon_mib']},'samples':rows}
 def growth(n):
  gate();time.sleep(1);result['growth'].append({'instances':n,**sample()});persist()
  if n in (0,50):
   import footprint,base64
   if product=='fork2':
    extra=list(pathlib.Path('/srv/fork2/data/template-memory-cache-v2').glob('*.ram'))
    for name in ['python','node','ruby']:
     cat=json.load(open('/srv/fork2/data/image-templates/'+name+'-warm512.json'));e=cat['template']['templateID'][len('e2b-snp-'):];ref=base64.urlsafe_b64decode(e+'='*(-len(e)%4)).decode();loc=ref.split('@location:')[1]
     for d in pathlib.Path('/srv/fork2/data/publications').glob('*/*/'+loc):extra.extend(d.glob('*.snapshot'))
   else:
    cat=json.load(open('/home/hong/src/research/fork2-print-compare-113/old/data/adapter-state.json.snapshot-preparation.json'));extra=[pathlib.Path(cat[name]['directory'])/'memory-ranges'for name in ['base','node','ruby']]
    extra.extend(pathlib.Path(p)for p in ['/home/hong/src/research/python-latest-113/assets/python-base-fork-opt3-v2.erofs','/home/hong/src/research/sixway-languages-20261117/assets/node/root.ext4','/home/hong/src/research/sixway-languages-20261117/assets/ruby/root.ext4'])
   result['growth'][-1]['footprint']=footprint.measure(product,extra);persist()
 def create():
  available=int(pathlib.Path('/proc/meminfo').read_text().split('MemAvailable:')[1].split()[0]);assert available>32*1024**2,'host memory guard'
  s=Sandbox.create(template,timeout=900,**opts);owned.append(s);persist();assert run(s,'printf READY')=='READY';gate()
 def clear():
  for s in list(owned):s.kill();owned.remove(s);persist()
  gate()
 def phase(mode):
  markers={s.sandbox_id:threading.Event() for s in owned};intervals={};code="""import os,time,sys
mode=sys.argv[1]
a=None
if mode!='python':
 a=bytearray(20*1024*1024)
 if mode in ('100','random'):
  for i in range(0,len(a),65536):a[i:i+65536]=os.urandom(65536) if mode=='random' else bytes([100])*65536
print('ALLOC_READY',flush=True)
time.sleep(20)
print('ALLOC_DONE',flush=True)
"""
  def task(s):
   chunks=[]
   def got(v):
    chunks.append(v);t=''.join(chunks)
    if 'ALLOC_READY\n' in t and not markers[s.sandbox_id].is_set():intervals[s.sandbox_id]={'ready_ns':time.monotonic_ns()};markers[s.sandbox_id].set()
    if 'ALLOC_DONE\n' in t:intervals[s.sandbox_id]['done_ns']=time.monotonic_ns()
   text=run(s,shlex.join(['exec','/usr/local/bin/python3','-c',code,mode]),on_stdout=got);assert text=='ALLOC_READY\nALLOC_DONE'
  with cf.ThreadPoolExecutor(max_workers=50) as pool:
   fs=[pool.submit(task,s) for s in owned];deadline=time.monotonic()+60
   for event in markers.values():assert event.wait(max(.001,deadline-time.monotonic())),'allocation readiness timeout'
   measurements=sample()
   for f in fs:f.result()
  left=max(x['ready_ns'] for x in intervals.values());right=min(x['done_ns'] for x in intervals.values());assert all(v['start_ns']>=left and v['end_ns']<=right for v in measurements['samples'])
  return {**measurements,'intervals':intervals,'mode':mode,'bytes_per_guest':0 if mode=='python' else 20*2**20,'guests':50}
 try:
  gate();growth(0)
  for i in range(50):
   create()
   if i+1 in [1,10,25,50]:growth(i+1);print(product,'growth',i+1,flush=True)
  for s in owned:assert run(s,'printf ALIVE')=='ALIVE'
  result['live_verified']=50;persist()
  result['guest_detail_after_measurements']=json.loads(run(owned[0],shlex.join(['/usr/local/bin/python3','-c',"import pathlib,os,json\nrows=[]\nfor p in pathlib.Path('/proc').glob('[0-9]*'):\n if p.name==str(os.getpid()):continue\n try:\n  v={}\n  for line in (p/'smaps_rollup').read_text().splitlines():\n   a=line.split()\n   if len(a)==3 and a[2]=='kB':v[a[0].rstrip(':')]=int(a[1])\n  rows.append(dict(pid=int(p.name),comm=(p/'comm').read_text().strip(),pss_kib=v.get('Pss',0),private_kib=v.get('Private_Clean',0)+v.get('Private_Dirty',0)))\n except OSError:pass\nprint(json.dumps(dict(processes=rows,meminfo=pathlib.Path('/proc/meminfo').read_text())))\n"])))
  persist()
  if os.environ.get('MEMORY_GROWTH_ONLY')=='1':
   result['success']=True;return
  for mode in ['zero','100','random']:
   if not owned:
    for _ in range(50):create()
   gate();result['arrays'][mode]={'before':sample()};persist()
   result['arrays'][mode]['python']=phase('python');persist()
   result['arrays'][mode]['allocated']=phase(mode);result['arrays'][mode]['increment_pss_mib']=result['arrays'][mode]['allocated']['median']['pss_mib']-result['arrays'][mode]['python']['median']['pss_mib'];persist();print(product,'array',mode,result['arrays'][mode]['increment_pss_mib'],flush=True)
   # Verify deleting one instance leaves a separate instance runnable.
   first=owned.pop(0);first.kill();persist();assert run(owned[-1],'printf SURVIVOR')=='SURVIVOR'
   clear();result['arrays'][mode]['after_delete']=sample();persist()
  result['success']=True
 except Exception:result['error']=traceback.format_exc();raise
 finally:
  for s in list(owned):
   try:s.kill();owned.remove(s)
   except Exception:result.setdefault('cleanup_errors',[]).append(traceback.format_exc())
  persist()
def main():
 lock=open('/run/skyrl-threeway-benchmark.lock','a');(None if os.environ.get("FORK2_FULL_LOCK_HELD")=="1" else fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB))
 for p in ['fork2','old']:
  args=[] if p=='fork2' else ['nsenter','--net=/run/netns/print113-old']
  subprocess.run(args+[sys.executable,__file__,p],check=True)
 print('MEMORY_BENCH_COMPLETE',flush=True)
if __name__=='__main__':
 if len(sys.argv)>1:worker(sys.argv[1])
 else:main()
