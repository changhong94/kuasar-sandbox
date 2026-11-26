from pathlib import Path
import subprocess as sp,time,json,fcntl,urllib.request
B=Path('/home/hong/src/research/sixway-aligned-20261117');lock=open('/run/skyrl-threeway-benchmark.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
c=json.loads(Path('/home/hong/src/research/sixway-formal-python-113/tools/config.json').read_text())['kuasar-mlink'];ctl=['nsenter','--net=/run/netns/'+c['netns']]+c['ctl'];ctl[-1]='300'
t=time.monotonic();started=time.time_ns()
sid=sp.check_output(ctl+['template','import','/home/hong/src/research/sandbox_fork/tools/generic-pool-10/base-common.erofs','--name','aligned-python-2cpu','--cpu-count','2','--memory-mb','2048','--disk-size-mb','1024','--scope','full'],text=True).strip()
(B/'results/mlink-template.json').write_text(json.dumps(dict(template=sid,started_unix_ns=started,elapsed_ms=(time.monotonic()-t)*1000),indent=2))
t=time.monotonic()
sp.run(ctl+['template','prewarm','set',sid,'--memory-state','full','--storage-min-ready','2','--storage-ready','2','--hot-ready-workers','0','--wait'],check=True)
(B/'results/mlink-prewarm.json').write_text(json.dumps(dict(template=sid,elapsed_ms=(time.monotonic()-t)*1000),indent=2))
print(sid)
