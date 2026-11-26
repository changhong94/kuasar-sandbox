import os
import pathlib,subprocess,json,time,fcntl
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2');p=R/'results/fork2.json'
if p.exists():p.rename(R/'results/memory-script-import-failure.json')
lock=open('/run/skyrl-threeway-benchmark.lock','a');(None if os.environ.get("FORK2_FULL_LOCK_HELD")=="1" else fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB))
subprocess.run(['/srv/fork2/bin/python-sdk','-u',str(R/'tools/memory.py'),'fork2'],check=True)
(R/'status.json').write_text(json.dumps({'phase':'initial-suites-finished','updated_ns':time.time_ns(),'complete':False}))
