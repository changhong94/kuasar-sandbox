from pathlib import Path
import fcntl,json,os,subprocess,time,sys
B=Path('/home/hong/src/research/sevenway-current-20261126/six');T=B/'tools';R=B/'results';PY='/home/hong/src/research/python-latest-113/venv/bin/python';cfg=json.loads((T/'config.json').read_text())
def run(name,args):
 if (B/(name+'-complete.json')).exists():return
 print('START',name,flush=True)
 with (B/(name+'.log')).open('w') as f:subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True)
 (B/(name+'-complete.json')).write_text(json.dumps({'time':time.time(),'arguments':args}))
 print('DONE',name,flush=True)
def reset_mlink():
 with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  c=cfg['kuasar-mlink'];ctl=['nsenter','--net=/run/netns/'+c['netns']]+c['ctl']
  assert not json.loads(subprocess.check_output(ctl+['list','--json'],text=True))
  subprocess.run(['systemctl','restart','bench-mlink-generic'],check=True)
  deadline=time.monotonic()+180
  while True:
   p=subprocess.run(ctl+['list','--json'],capture_output=True,text=True)
   if not p.returncode:assert not json.loads(p.stdout);break
   if time.monotonic()>deadline:raise TimeoutError('mlink API preparation')
   time.sleep(1)
  subprocess.run([PY,str(T/'switch-language.py'),str(T/'config.json'),'python',str(B/'preparation/serial')],check=True)
while not (B/'parallel-startup-deployed.json').exists():time.sleep(10)
if (R/'growth').is_symlink():(R/'growth').unlink()
run('fork-template-prepare',['nsenter','--net=/run/netns/py113-fork',PY,str(B/'prepare_fork_templates.py')])
if not (B/'matrix-complete.json').exists():reset_mlink()
run('matrix',[PY,str(B/'run_matrix.py')])
run('live-formal',['nsenter','--net=/run/netns/py113-fork',PY,str(B/'live_fork.py'),'--languages','python','--samples','50','--out',str(R/'live-formal')])
run('analyze-live',[PY,str(B/'analyze_live.py'),str(R/'live-formal')])
run('summarize-startup',[PY,str(B/'summarize_modes.py'),str(B)])
if not (B/'resource-full-complete.json').exists():reset_mlink()
run('resource-full',[PY,str(T/'run_full.py')])
# Restore a 64-ready idle baseline after retained-instance experiments.
if not (B/'snapshots-formal-complete.json').exists():reset_mlink()
run('snapshots-formal',[PY,str(B/'snapshot_bench.py')])
run('read-resource',[PY,str(B/'read_resource_suite.py')])
run('pool-memory',[PY,str(B/'pool_memory.py')])
run('disk-backing',['nsenter','--net=/run/netns/py113-fork',PY,str(B/'verify_disk_backing.py')])
(B/'validation-batches-complete.json').write_text(json.dumps({'completed_unix':time.time(),'fresh':True}))
