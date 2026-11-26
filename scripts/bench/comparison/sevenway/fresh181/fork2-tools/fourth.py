import pathlib,subprocess,json,time,sqlite3
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2');T=R/'tools'
def run(*a):subprocess.run(a,check=True)
while subprocess.run(['systemctl','is-active','--quiet','fork2-sevenway-third']).returncode==0:time.sleep(3)
assert json.loads((R/'status.json').read_text())['phase']=='third-suites-finished'
run('/usr/bin/python3',str(T/'resume_paced.py'))
(R/'results/storage.json').rename(R/'results/storage-initial-scope.json')
run('/srv/fork2/bin/python-sdk','-u',str(T/'storage.py'),'--count','3','--output',str(R/'results/storage.json'))
(R/'status.json').write_text(json.dumps({'phase':'lifecycle','complete':False}))
run('/srv/fork2/bin/python-sdk','-u',str(T/'lifecycle.py'))
run('python3',str(T/'audit_idle_resources.py'))
with sqlite3.connect('file:/srv/fork2/data/base/node-ctl.db?mode=ro',uri=True)as d:assert d.execute('select count(*) from sandboxes').fetchone()[0]==0
run('systemctl','stop','fork2-conductor','fork2-proxy')
units=[x.split()[0]for x in subprocess.check_output(['systemctl','list-units','fork2-runner@*','--plain','--no-legend'],text=True).splitlines()if x.startswith('fork2-runner@')]
if units:run('systemctl','stop',*units)
run('systemctl','stop','fork2-shared','fork2-store','fork2-switch')
remaining=subprocess.check_output(['systemctl','list-units','fork2-*','--state=running','--plain','--no-legend'],text=True)
active=[s for s in remaining.splitlines()if 'fork2-sevenway-'not in s];assert not active,active
(R/'cleanup.json').write_text(json.dumps({'sandboxes_remaining':0,'runtime_services_running':active,'other_known_process_alive':pathlib.Path('/proc/957181').exists(),'finished_ns':time.time_ns()},indent=2))
(R/'status.json').write_text(json.dumps({'phase':'tests-finished-report-pending','complete':False,'finished_ns':time.time_ns()}))
print('ALL_TEST_SUITES_COMPLETE',flush=True)
