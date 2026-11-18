from pathlib import Path
import json,subprocess as sp,sys,fcntl
B=Path('/home/hong/src/research/sixway-aligned-20261117');cfg=json.loads((B/'tools/config.json').read_text());lock=open('/run/skyrl-threeway-benchmark.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
for n,c in cfg.items():
 if n.startswith('_'):continue
 sp.run(['nsenter','--net=/run/netns/'+c['netns'],sys.executable,str(B/'tools/preflight.py'),n],check=True)
