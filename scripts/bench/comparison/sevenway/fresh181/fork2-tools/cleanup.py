import pathlib,sqlite3,subprocess,json,time,hashlib
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2/results')
deadline=time.monotonic()+180
while True:
 with sqlite3.connect('file:/srv/fork2/data/base/node-ctl.db?mode=ro',uri=True)as db:
  assert db.execute('select count(*)from sandboxes').fetchone()[0]==0
 raw=subprocess.check_output(['curl','-sf','--max-time','3','--unix-socket','/run/fork2/node.sock','http://localhost/internal/admin/resource-pressure'])
 pools=json.loads(raw)['runner_pools']
 if any(p.get('name')=='prepared' and p.get('states')=={'idle':64} for p in pools):break
 if time.monotonic()>=deadline:raise TimeoutError('64 idle slots did not settle before final audit')
 time.sleep(.05)
with sqlite3.connect('file:/srv/fork2/data/base/node-ctl.db?mode=ro',uri=True)as db:
 n=db.execute('select count(*)from sandboxes').fetchone()[0];assert n==0
 leases=db.execute('select count(*)from prepared_vm_leases').fetchone()[0];assert leases==64
raw=subprocess.check_output(['curl','-sf','--unix-socket','/run/fork2/node.sock','http://localhost/internal/admin/resource-pressure'])
status=json.loads(raw);prepared=next(p for p in status['runner_pools']if p['name']=='prepared');assert prepared['states']=={'idle':64}
pid=int(subprocess.check_output(['systemctl','show','fork2-shared','-p','MainPID','--value']))
audit=dict(sandboxes_remaining=n,prepared_leases=leases,prepared_states=prepared['states'],controller_fds=len(list(pathlib.Path('/proc',str(pid),'fd').iterdir())),other_known_process_alive=pathlib.Path('/proc/957181').exists(),finished_ns=time.time_ns())
(R/'audit.json').write_text(json.dumps(audit,indent=2))
run=lambda *a:subprocess.run(a,check=True,stdout=subprocess.DEVNULL)
run('systemctl','stop','fork2-conductor','fork2-proxy')
u=[x.split()[0]for x in subprocess.check_output(['systemctl','list-units','fork2-runner@*','--plain','--no-legend'],text=True).splitlines()if x.startswith('fork2-runner@')]
if u:run('systemctl','stop',*u)
run('systemctl','stop','fork2-shared','fork2-store','fork2-switch')
units=subprocess.check_output(['systemctl','list-units','fork2-*','--state=running','--plain','--no-legend'],text=True);assert not [l for l in units.splitlines()if 'fork2-full-current' not in l],units
result=dict(audit,running_fork2_units=[],binary_sha256={p:hashlib.sha256((pathlib.Path('/srv/fork2/bin')/p).read_bytes()).hexdigest() for p in ['cloud-hypervisor','node-ctl','node-vm-runner','node-runner','node-checkpoint','sandbox-ctl','node-register']})
(R/'cleanup.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
