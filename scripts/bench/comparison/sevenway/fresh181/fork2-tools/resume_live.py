import subprocess,json,pathlib,time
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2')
subprocess.run(['/srv/fork2/bin/python-sdk','-u',str(R/'tools/live_fork.py')],check=True)
(R/'status.json').write_text(json.dumps({'phase':'live-fork-finished-pending-paced-repair','complete':False,'updated_ns':time.time_ns()}))
