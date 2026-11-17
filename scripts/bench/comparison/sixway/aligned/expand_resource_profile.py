from pathlib import Path
import subprocess as sp,time,json,fcntl
B=Path('/home/hong/src/research/sixway-aligned-20261117');F=Path('/home/hong/src/research/python-latest-113');lock=open('/run/skyrl-threeway-benchmark.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
cfg=json.loads((B/'tools/config.json').read_text());assert len(json.loads((B/'results/startup/summary.json').read_text()))==6
# Both APIs are isolated to this bench; verify no active leases before restarting.
s=sp.check_output(['nsenter','--net=/run/netns/bench113-m-generic']+cfg['kuasar-mlink']['ctl']+['list','--json'],text=True);assert json.loads(s)==[]
records=json.loads((F/'data/fork/adapter-state.json').read_text());assert len(records)==2 and all(r['pool_state']=='ready' for r in records.values())
t=time.monotonic();wall=time.time_ns();p=B/'tools/reset-resource-fork.py';p.write_text((B/'tools/reset-fork.py').read_text().replace('capacity=2','capacity=64'))
sp.run(['nsenter','--net=/run/netns/py113-fork','python3',str(p)],check=True)
p=Path('/home/hong/deploy/mlink-generic/start.sh');s=p.read_text();(B/'backups/start-startup-profile.sh').write_text(s);p.write_text(s.replace('write_node_configs 2 1000 2 2 2','write_node_configs 64 1000 2 2 64'))
p=Path('/home/hong/deploy/mlink-generic/mlink-env.sh');s=p.read_text();p.write_text(s.replace('POOL_CAPACITY=2','POOL_CAPACITY=64'))
sp.run(['systemctl','restart','bench-mlink-generic'],check=True)
(B/'results/resource-profile-preparation.json').write_text(json.dumps(dict(started_unix_ns=wall,service_reset_ms=(time.monotonic()-t)*1000,startup_capacity=2,resource_capacity=64,note='Expanded only after startup measurements; required for 50 simultaneous sandboxes. Pool wait recorded separately.'),indent=2))
