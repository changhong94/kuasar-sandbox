from pathlib import Path
import subprocess as sp,time,json,fcntl,hashlib
B=Path('/home/hong/src/research/sixway-aligned-20261117');F=Path('/home/hong/src/research/python-latest-113')
lock=open('/run/skyrl-threeway-benchmark.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
records=[]
def edit(path,replacements):
 p=Path(path);old=p.read_text(); backup=B/'backups'/p.name
 assert not backup.exists(),backup
 backup.write_text(old)
 for a,b in replacements:
  assert a in old,(p,a)
  old=old.replace(a,b)
 p.write_text(old)
def run(name,args):
 t=time.monotonic();wall=time.time_ns()
 with (B/'results'/(name+'.log')).open('w') as log:r=sp.run(args,stdout=log,stderr=sp.STDOUT)
 records.append(dict(name=name,started_unix_ns=wall,elapsed_ms=(time.monotonic()-t)*1000,returncode=r.returncode))
 (B/'results/deployment-preparation.json').write_text(json.dumps(records,indent=2));assert r.returncode==0,name
# Dedicated bench deployments only; inventories checked empty immediately before this script.
for path in ['/home/hong/deploy/comparison/kuasar-state/demo_e2b.sh','/home/hong/deploy/private-pilot/uffd-serve.sh']:
 changes=[('capacity: { cpu: 1, memory: 2GiB }','capacity: { cpu: 2, memory: 2GiB }'),('allocatable: { cpu: 1, memory: 2GiB }','allocatable: { cpu: 2, memory: 2GiB }'),('python3 -m http.server 8000 --directory /home/user/site','/bin/sleep infinity')]
 if 'uffd' in path:changes.append(('cpu_count=1,','cpu_count=2,'))
 edit(path,changes)
edit(F/'deploy/fork/config.toml',[('vcpus=1','vcpus=2')])
edit(F/'deploy/fork/supervisor.py',[("'--cpu-count','1'","'--cpu-count','2'")])
edit('/home/hong/deploy/mlink-generic/mlink-env.sh',[('PROFILE_CPU_COUNT=1','PROFILE_CPU_COUNT=2'),('POOL_CAPACITY=64','POOL_CAPACITY=2')])
edit('/home/hong/deploy/mlink-generic/start.sh',[('write_node_configs 64 1000 2 2 64','write_node_configs 2 1000 2 2 2')])
p=F/'tools/reset-fork.py';(B/'tools/reset-fork.py').write_text(p.read_text().replace('capacity=64','capacity=2'))
run('fork-reset',['nsenter','--net=/run/netns/py113-fork','python3',str(B/'tools/reset-fork.py')])
for unit in ['kuasar-comparison-node','bench-private-uffd-serve','bench-mlink-generic']:
 run('restart-'+unit,['systemctl','restart',unit])
