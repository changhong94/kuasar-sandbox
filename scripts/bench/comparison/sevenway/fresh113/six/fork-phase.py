from pathlib import Path
import subprocess as sp,os,sys,json,time,hashlib,secrets,shutil
r=Path(__file__).resolve().parent; d=r/'deployment/fork'; data=r/'runtime-media/volume/fork'; runtime=Path('/run/sx19fork'); old=Path('/home/hong/src/research/python-latest-113'); rev=Path('/home/hong/src/research/report-revision-113'); q=Path('/home/hong/src/research/sandbox_fork/kuasar-io/kuasar');ns='sixway19-fork'; seed='sixway19-seed'; sid='sx19seed001'; e=r/'attempts'/('fork-live-'+str(time.time_ns()));e.mkdir(); os.umask(0o077)
def run(*a,**kw):return sp.run(a,check=True,**kw)
def write(p,obj):p.write_text(json.dumps(obj,indent=2))
status=dict(section='fork-live',batch='python',start=time.time(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),attempt=str(e))
def mark(phase):
 status['phase']=phase;status['updated']=time.time();write(e/'checkpoint.json',status)
def main():
 mark('private deployment');j=json.loads((r/'ownership.json').read_text()); units=['sixway-20261119-'+s+'.service' for s in ['store','cache','fork-api','live-runner']]
 for unit in units[:-1]:assert sp.check_output(['systemctl','show','-p','LoadState','--value',unit],text=True).strip()=='not-found'
 assert not (Path('/run/netns')/seed).exists()
 j['fork_phase']={'units':units,'seed_netns':seed,'seed_id':sid,'bridge':'sx19forkbr','bridge_netns':ns,'ipam':str(data/'ipam'),'runtime_data':str(data),'private_config':str(d),'original':'absent','created_instance_evidence':[str(data/'adapter-state.json'),str(data/'state'),str(e)],'sockets':[str(runtime/x) for x in ('health.sock','cache.sock','store.sock')],'cni_network':'sx19fork','api_listener':{'netns':ns,'port':18887,'address':'127.0.0.1'}}
 write(r/'ownership.json',j)
 for name in ['api-key','images.json']:shutil.copyfile(old/'deploy/fork'/name,d/name)
 spec=json.loads((r/'tools/config.json').read_text());cat=json.loads((d/'images.json').read_text())
 for k,v in cat.items():
  assert spec['_languages']['python' if k=='base' else k]['digest']==v['manifest']
  assert sp.check_output(['sha256sum',v['disk']],text=True).split()[0]==v['sha256']
 run('cp','--sparse=always',old/'data/fork/writable-template.raw',data/'writable-template.raw')
 cni=json.loads((old/'deploy/fork/cni.json').read_text());cni.update(name='sx19fork',bridge='sx19forkbr');cni['ipam']['dataDir']=str(data/'ipam');write(d/'cni.json',cni)
 for kind in ['store','cache','manifest']:
  conf=(rev/'private'/(kind+'.yaml')).read_text().replace('/run/bench-revision113',str(runtime)).replace(str(rev)+'/rocks-cache',str(data/'rocks-cache')).replace(str(rev)+'/store',str(data/'store'))
  if kind=='manifest':
   import re
   conf,n=re.subn(r'(?m)^(  key:).*$',lambda m:m[1]+' "'+secrets.token_hex(32)+'"',conf);assert n==1
  assert str(rev) not in conf and '/run/bench-revision113' not in conf
  (d/(kind+'.yaml')).write_text(conf)
 run(rev/'bin/store-ctl','init','--config',d/'store.yaml','--generation','G1',stdout=sp.DEVNULL)
 for kind,unit in zip(['store','cache'],units):
  run('systemd-run','--unit='+unit,'-p','MemoryMax=8G','/usr/bin/env',rev/'bin'/(kind+'-ctl'),'serve','--config',d/(kind+'.yaml'))
 for i in range(100):
  if sp.run([rev/'bin/cache-ctl','ping','--endpoint','unix://'+str(runtime/'health.sock')],capture_output=True).returncode==0:break
  time.sleep(.1)
 else:raise RuntimeError('cache readiness')
 mark('seed and reserve preparation')
 # Retain the reviewed seed preparation logic and run its HTTP adapter against the new sandboxer.
 src=(old/'deploy/fork/supervisor.py').read_text();part=src[src.index("sid='py113seed001'"):]
 for a,b in [('py113seed001',sid),('py113-fork-seed',seed),("P/'admin.sock'","Path('/run/sx19fork/admin.sock')"),("P/'bin'/","(B/'deploy/fork/bin')/")]:part=part.replace(a,b)
 head=f'import sys,subprocess as sp,json,os,time,signal\nfrom pathlib import Path\nP=Path({str(d)!r});DATA=Path({str(data)!r});B=Path({str(old)!r});Q=Path({str(q)!r});children=[]\nsys.path.insert(0,str(Q/"integrations/e2b"));import vm_rpc\n'
 (d/'api.py').write_text(head+part)
 env=dict(KUASAR_FORK_RUNTIME_DIR=str(runtime),KUASAR_SNAPSHOT_POOL_ROOT=str(data/'snapshot-templates'),E2B_DURABLE_STORE='sqlite',E2B_DURABLE_SQLITE_ROOT=str(data/'sqlite'),E2B_TEMPLATE_POOL_SIZE='64',E2B_TEMPLATE_POOL_WORKERS='8',E2B_IMAGE_CATALOG=str(d/'images.json'),E2B_SNAPSHOT_POOL='1',E2B_TRACE_TIMING='1',E2B_WRITABLE_BASE=str(data/'writable-template.raw'),E2B_TEMPLATE_METADATA='1',E2B_TEMPLATE_READ_CACHE_BYTES='536870912',CH_RESTORE_TIMING='1',CH_FORK_TIMING='1',E2B_MANIFEST_CONFIG=str(d/'manifest.yaml'),E2B_MANIFEST_RAW=str(rev/'bin/manifest-raw'),KUASAR_SNAPSHOT_PIPELINE_CONTROL='0')
 log=e/'api.log'
 run('systemd-run','--unit='+units[2],'-p','NetworkNamespacePath=/run/netns/'+ns,'-p','StandardOutput=append:'+str(log),'-p','StandardError=inherit','-p','LimitNOFILE=65536',*['--setenv='+k+'='+v for k,v in env.items()],'/usr/bin/python3',d/'api.py')
 spec['kuasar-fork'].update(netns=ns,key_file=str(d/'api-key'),resource_cgroup_patterns=[units[2], 'sixway-20261119-fork-vmm']);write(d/'benchmark-config.json',spec)
 live=(r/'live_fork.py').read_text().replace("TOOLS/'config.json'",repr(str(d/'benchmark-config.json'))).replace('Path('+repr(str(d/'benchmark-config.json'))+')','Path('+repr(str(d/'benchmark-config.json'))+')').replace('('+repr(str(d/'benchmark-config.json'))+').read_text()', 'Path('+repr(str(d/'benchmark-config.json'))+').read_text()').replace('/var/log/bench-python113-refill-scale-fixed.log',str(log)).replace("fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)","assert os.environ['SIXWAY_OUTER_LOCK']=='1'").replace("'bench-python113-fork'",repr(units[2]))
 (d/'live.py').write_text(live)
 from urllib.request import Request,urlopen
 req=Request(spec['kuasar-fork']['api_url']+'/template-pool',headers={'X-API-Key':(d/'api-key').read_text().strip()})
 for i in range(600):
  assert sp.run(['systemctl','is-active','--quiet',units[2]]).returncode==0,'fork API unit exited'
  try:
   with urlopen(req,timeout=2) as response:pool=json.load(response)
   write(e/'pool.json',pool)
   if pool.get('ready')==64 and pool.get('preparing',0)==0:break
  except OSError:pass
  time.sleep(1)
 else:raise TimeoutError('64 reserve readiness')
 mark('50 live-parent samples plus excluded warmup')
 run(old/'venv/bin/python',d/'live.py','--languages','python','--samples','50','--out',e/'samples',env={**os.environ,'SIXWAY_OUTER_LOCK':'1','PYTHONPATH':str(r/'tools')})
 status['exit']=0
try:main()
except Exception as error:status.update(exit=1,error=repr(error));raise
finally:status['end']=time.time();write(e/'checkpoint.json',status)
