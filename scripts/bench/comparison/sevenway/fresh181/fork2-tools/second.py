import pathlib,subprocess,time,json,sqlite3
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2');T=R/'tools';P='/srv/fork2/bin/python-sdk'
def run(*a):subprocess.run(a,check=True)
def status(s): (R/'status.json').write_text(json.dumps({'phase':s,'updated_ns':time.time_ns(),'complete':False}))
while subprocess.run(['systemctl','is-active','--quiet','fork2-sevenway-initial']).returncode==0:time.sleep(3)
assert json.loads((R/'status.json').read_text())['phase']=='initial-suites-finished'
for interval in [0,10,25,50,100]:
 status('256-requests-'+str(interval));run(P,'-u',str(T/'burst_latest.py'),str(R/'results/paced'/str(interval)),str(interval))
status('live-fork')
run('python3',str(T/'audit_idle_resources.py'))
run(P,'-u',str(T/'live_fork.py'))
run('python3',str(T/'audit_idle_resources.py'))
status('second-suites-finished');print('SECOND_SUITES_COMPLETE',flush=True)
