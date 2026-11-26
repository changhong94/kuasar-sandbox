import pathlib,json,time,subprocess
R=pathlib.Path('/home/hong/src/research/sevenway-current-20261126/fork2');T=R/'tools'
while subprocess.run(['systemctl','is-active','--quiet','fork2-sevenway-supplement']).returncode==0:time.sleep(3)
assert json.loads((R/'status.json').read_text())['phase']=='supplement-finished-review-pending'
def state():return json.loads(subprocess.check_output(['curl','--fail','--silent','--max-time','3','--unix-socket','/run/fork2/node.sock','http://localhost/internal/admin/resource-pressure'],timeout=5))
(R/'results/preparation-history-before.json').write_text(json.dumps(state()))
subprocess.run(['/srv/fork2/bin/python-sdk','-u',str(T/'burst_latest.py'),str(R/'results/timing-burst/0'),'0'],check=True)
(R/'results/preparation-history-after.json').write_text(json.dumps(state()))
# Reuse the previously verified scoped cleanup, without rerunning lifecycle.
s=(T/'resume_lifecycle.py').read_text();cleanup=s[s.index('with sqlite3.connect'):]
import sqlite3
run=lambda *a:subprocess.run(a,check=True)
exec(cleanup)
