import pathlib,subprocess,time,json,sqlite3
R=pathlib.Path('/home/hong/src/research/sevenway-current-20261126/fork2');T=R/'tools';P='/srv/fork2/bin/python-sdk'
def run(*a):subprocess.run(a,check=True)
def status(s): (R/'status.json').write_text(json.dumps({'phase':s,'updated_ns':time.time_ns(),'complete':False}))
for interval in [10,25,50,100]:
 target=R/'results/paced'/str(interval)
 if target.exists():target.rename(target.with_name(str(interval)+'-failed-'+str(time.time_ns())))
 status('256-requests-'+str(interval));run(P,'-u',str(T/'burst_latest.py'),str(R/'results/paced'/str(interval)),str(interval))
status('second-suites-finished');print('SECOND_SUITES_COMPLETE',flush=True)
