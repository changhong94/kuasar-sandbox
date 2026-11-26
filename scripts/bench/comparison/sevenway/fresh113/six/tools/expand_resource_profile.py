from pathlib import Path
import subprocess as sp,time,json,fcntl
B=Path('/home/hong/src/research/sevenway-current-20261126/six');F=Path('/home/hong/src/research/python-latest-113');lock=open('/run/skyrl-threeway-benchmark.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
cfg=json.loads((B/'tools/config.json').read_text());assert len(json.loads((B/'results/matrix/python/summary.json').read_text()))==6
# Both APIs are isolated to this bench; verify no active leases before restarting.
s=sp.check_output(['nsenter','--net=/run/netns/bench113-m-generic']+cfg['kuasar-mlink']['ctl']+['list','--json'],text=True);assert json.loads(s)==[]
records=json.loads((F/'data/fork/adapter-state.json').read_text());assert all(r.get('pool_state')=='ready' for r in records.values())
t=time.monotonic();wall=time.time_ns();p=B/'tools/reset-resource-fork.py';p.write_text((B/'tools/reset-fork.py').read_text().replace('capacity=2','capacity=64'))
sp.run(['nsenter','--net=/run/netns/py113-fork','env','POOL_RESET_STOPPED=1','python3',str(p)],check=True)
sp.run(['python3','/home/hong/src/research/ready-opt-staging-113/gc-offline.py'],check=True)
with Path('/etc/systemd/system/bench-python113-fork.service.d/ready-opt.conf').open('a') as f:f.write('Environment=E2B_TEMPLATE_POOL_SIZE=64\n')
sp.run(['systemctl','daemon-reload'],check=True)
sp.run(['systemctl','start','bench-python113-fork'],check=True)
p=Path('/home/hong/deploy/mlink-generic/start.sh');s=p.read_text();(B/'backups/start-startup-profile.sh').write_text(s);p.write_text(s.replace('write_node_configs 2 1000 2 2 2','write_node_configs 64 1000 2 2 64'))
p=Path('/home/hong/deploy/mlink-generic/mlink-env.sh');s=p.read_text();(B/'backups/mlink-startup-env.sh').write_text(s);p.write_text(s.replace('POOL_CAPACITY=2','POOL_CAPACITY=64'))
sp.run(['systemctl','restart','bench-mlink-generic'],check=True)
(B/'results/resource-profile-preparation.json').write_text(json.dumps(dict(started_unix_ns=wall,service_reset_ms=(time.monotonic()-t)*1000,startup_capacity=2,resource_capacity=64,note='Expanded only after startup measurements; required for 50 simultaneous sandboxes. Pool wait recorded separately.'),indent=2))

# Wait outside timing and retain the capacity-64 preparation cost.
for _ in range(300):
 try:
  sp.run(['nsenter','--net=/run/netns/'+cfg['kuasar-mlink']['netns']]+cfg['kuasar-mlink']['ctl']+['template','prewarm','set',cfg['kuasar-mlink']['template'],'--memory-state','full','--storage-min-ready','64','--storage-ready','64','--hot-ready-workers','0','--wait'],check=True,capture_output=True)
  break
 except sp.CalledProcessError:time.sleep(1)
else:raise RuntimeError('mlink resource prewarm unavailable')
for name in ['kuasar-fork','kuasar-mlink']:
 code="import sys,json;sys.path.insert(0,"+repr(str(B/'tools'))+");from pool_gate import wait;c=json.load(open("+repr(str(B/'tools/config.json'))+"));print(json.dumps(wait(c["+repr(name)+"],capacity=64,timeout=600)))"
 result=sp.check_output(['nsenter','--net=/run/netns/'+cfg[name]['netns'],'python3','-c',code],text=True)
 (B/'results'/('resource-ready-'+name+'.json')).write_text(result)
(B/'results/resource-preparation-total.json').write_text(json.dumps({'elapsed_ms':(time.monotonic()-t)*1000,'capacity':64}))
