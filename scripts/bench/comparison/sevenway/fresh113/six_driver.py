from pathlib import Path
import subprocess as sp,json,time,os,fcntl,traceback
R=Path('/home/hong/src/research/sevenway-current-20261126');B=R/'six';T=B/'tools';PY='/home/hong/src/research/python-latest-113/venv/bin/python'
os.environ.update(SIXWAY_ROOT=str(B),NO_PROXY='*',no_proxy='*')
records=[]
if (B/'status.json').exists():records=json.loads((B/'status.json').read_text()).get('stages',[])
def status(phase,**kw):
 p=B/'status.json';q=p.with_suffix('.tmp');q.write_text(json.dumps(dict(phase=phase,stages=records,updated_unix=time.time(),complete=False,**kw),indent=2));q.replace(p)
def run(name,args):
 if any(x['name']==name and x['exit']==0 for x in records):return
 status(name);start=time.time();log=B/'logs'/(name+'.log')
 if log.exists():log.rename(log.with_name(log.name+'.'+str(time.time_ns())))
 with log.open('w') as f:r=sp.run(args,stdout=f,stderr=sp.STDOUT)
 records.append(dict(name=name,start=start,end=time.time(),exit=r.returncode));status(name+'-finished')
 assert r.returncode==0,(name,r.returncode)
def cmd(*a):sp.run(a,check=True)
try:
 status('waiting-for-fork2')
 while True:
  state=R/'fork2/status.json'
  if not state.exists():time.sleep(1);continue
  x=json.loads(state.read_text())
  if x.get('complete'):break
  if x.get('phase')=='failed-needs-review':raise RuntimeError('fork2 needs repair before six-product rollout')
  time.sleep(10)
 # Read-only namespace ownership guards before reviving our retired deployment.
 with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  cubelet_pid=sp.check_output(['systemctl','show','cube-sandbox-cubelet','-p','MainPID','--value'],text=True).strip()
  owned_containers=[]
  probe=sp.run(['docker','-H','unix:///run/cube-comparison/docker.sock','ps','--no-trunc','--format','{{.ID}} {{.Names}}'],capture_output=True,text=True)
  if probe.returncode==0:
   for line in probe.stdout.splitlines():
    ident,name=line.split()
    if name in ['sevenway-cube-containerd','cube-sandbox-mysql','cube-sandbox-minio','cube-sandbox-redis','cube-proxy-coredns','cube-proxy','cube-egress','cube-lifecycle-manager']:owned_containers.append(ident)
  for n in ['bench113','bench113-u','bench113-m-generic','py113-fork']:
   p=Path('/run/netns')/n
   if p.exists():
    ino=p.stat().st_ino;owners=[]
    for q in Path('/proc').glob('[0-9]*'):
     try:
      if (q/'ns/net').stat().st_ino==ino:
       cg=(q/'cgroup').read_text()
       resumed_support=any(x['name']=='support' and x['exit']==0 for x in records)
       allowed=any('/'+u+'.service' in cg for u in ['sevenway-cube-containerd','cube-sandbox-mysql','cube-sandbox-minio','cube-sandbox-redis','bench-cube-docker','bench-fixture-registry','kuasar-comparison-node','kuasar-comparison-prep','bench-private-uffd-prep','bench-private-uffd-serve','agentenv-comparison','bench-mlink-generic','bench-python113-fork','cube-sandbox-cubemaster','cube-sandbox-cube-api','cube-sandbox-cube-templatecenter','cube-sandbox-cubelet','cube-sandbox-cubeops','cube-sandbox-webui','cube-sandbox-cube-egress','cube-sandbox-coredns','cube-sandbox-dns','cube-sandbox-cube-proxy','cube-sandbox-cube-lifecycle-manager','cube-sandbox-s3lvol','bench113-dns-egress']) or any('/docker-'+ident+'.scope' in cg or '/'+ident+'/' in cg for ident in owned_containers)
       if q.name==cubelet_pid and (q/'comm').read_text().strip()=='cubelet':allowed=True
       if not (resumed_support and allowed):owners.append(q.name)
     except OSError:pass
    assert not owners,(n,owners)
  run('layout',['systemctl','start','bench113-layout'])
  p=Path('/run/netns/py113-fork')
  if not p.exists():cmd('ip','netns','add','py113-fork');cmd('ip','-n','py113-fork','link','set','lo','up')
  run('support',['systemctl','start','bench-cube-docker','bench-fixture-registry'])
  # Existing authenticated manifests keep their existing storage/key configuration.
  private=Path('/home/hong/src/research/report-revision-113/private');bindir=private.parent/'bin'
  Path('/run/bench-revision113').mkdir(mode=0o700,exist_ok=True)
  for kind in ['store','cache']:
   unit='bench-revision113-'+kind
   if sp.run(['systemctl','is-active','--quiet',unit]).returncode:
    run(unit,['systemd-run','--unit',unit,'--collect','--property=MemoryMax=8G','/bin/bash','-c','exec "$1" serve --config "$2"','bash',str(bindir/(kind+'-ctl')),str(private/(kind+'.yaml'))])
  for name,unit in [('off','kuasar-comparison-node'),('uffd','bench-private-uffd-serve'),('agentenv','agentenv-comparison'),('mlink','bench-mlink-generic'),('cube','cube-sandbox-control.target'),('fork','bench-python113-fork')]:
   run('deploy-'+name,['systemctl','start',unit])
 run('refresh-clients',[PY,str(B/'refresh_clients.py')])
 run('rocksdb-cache-routing',[PY,'/home/hong/src/research/report-revision-113/prepare_rocks.py'])
 import shutil
 shutil.copy2('/home/hong/src/research/report-revision-113/remote-cache.json',B/'remote-cache.json')
 for product in ['kuasar-off','kuasar-uffd']:
  run('native-export-'+product,[PY,str(B/'prepare_native.py'),product])
 run('native-export-closure',[PY,str(B/'complete_native.py')])
 run('preflight',[PY,str(T/'run_preflight.py')])
 run('fork-template-prepare',['nsenter','--net=/run/netns/py113-fork',PY,str(B/'prepare_fork_templates.py')])
 run('startup-matrix',[PY,str(B/'run_matrix.py')])
 run('select-python',[PY,str(T/'switch-language.py'),str(T/'config.json'),'python',str(B/'preparation/resources')])
 run('resources-storage-memory',[PY,str(T/'run_full.py')])
 run('pause-restore',[PY,str(B/'snapshot_bench.py')])
 run('pool-memory',[PY,str(B/'pool_memory.py')])
 run('live-fork',['nsenter','--net=/run/netns/py113-fork',PY,str(B/'live_fork.py'),'--languages','python','--samples','50','--out',str(B/'results/live-formal')])
 run('burst-paced',[PY,str(B/'run_paced.py')])
 status('measurements-finished-awaiting-audit')
except BaseException as e:
 status('failed-needs-review',error=repr(e));traceback.print_exc();raise
