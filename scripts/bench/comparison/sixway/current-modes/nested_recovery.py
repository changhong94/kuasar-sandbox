"""Fresh host-reboot verification in the already-owned isolated nested host."""
from pathlib import Path
import fcntl,hashlib,json,os,shutil,subprocess,time,tomllib
B=Path('/home/hong/src/research/report-revision-113');N=Path('/home/hong/src/research/fork-features-113/nested');F=Path('/home/hong/src/research/python-latest-113');root=N/'root';ssh=str(N/'ssh')
def run(argv,**kw):return subprocess.run(list(map(str,argv)),check=True,**kw)
def nested(command,**kw):return run([ssh,command],**kw)
def ready():
 deadline=time.monotonic()+300
 probe="""import json,urllib.request
from pathlib import Path
p=Path('/home/hong/src/research/python-latest-113/deploy/fork')
r=urllib.request.Request('http://127.0.0.1:18887/template-pool',headers={'X-API-Key':(p/'api-key').read_text().strip()})
s=json.load(urllib.request.urlopen(r,timeout=2));assert s['capacity']==2 and s['refill_delay_ms']==0
"""
 while time.monotonic()<deadline:
  try:
   r=subprocess.run([ssh,'python3 -'],input=probe,text=True,capture_output=True,timeout=8)
   if r.returncode==0:return
  except subprocess.TimeoutExpired:pass
  time.sleep(2)
 raise TimeoutError('owned nested host/API readiness')
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert not (N/'qemu.pid').exists(),'inspect an existing nested VM before changing its disk'
 assert subprocess.run(['findmnt','--mountpoint',str(root)],stdout=subprocess.DEVNULL).returncode!=0
 for p in Path('/proc').glob('[0-9]*/cmdline'):
  try:args=p.read_bytes().split(b'\0')
  except OSError:continue
  assert not (args and b'qemu' in args[0] and str(N/'root.raw').encode() in b' '.join(args)), 'owned raw disk is in use'
 run(['mount','-o','loop',N/'root.raw',root])
 try:
  for source in [F/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b',F/'deploy/fork/bin',F/'assets']:
   destination=root/str(source).lstrip('/');destination.mkdir(parents=True,exist_ok=True)
   run(['rsync','-aS','--exclude=__pycache__',str(source)+'/',str(destination)+'/'])
  config=F/'deploy/fork/config.toml'
  runtime=Path(tomllib.loads(config.read_text())['hypervisor']['image_path'])
  target=root/str(runtime).lstrip('/');target.parent.mkdir(parents=True,exist_ok=True)
  run(['rsync','-aS',runtime,target])
  shutil.copy2(config,root/str(config).lstrip('/'))
  (B/'nested-runtime-provenance.json').write_text(json.dumps({'source':str(runtime),'sha256':hashlib.sha256(runtime.read_bytes()).hexdigest(),'copied_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'config_sha256':hashlib.sha256(config.read_bytes()).hexdigest()},indent=2))
  shutil.copy2(B/'test_reboot_guest.py',root/'root/test_reboot_guest.py')
  unit=root/'etc/systemd/system/nested-fork.service'
  s=unit.read_text();s=s.replace('Environment=E2B_TEMPLATE_POOL_REFILL_DELAY_MS=1000\n','');unit.write_text(s)
 finally:run(['umount',root])
 run(['sh',N/'launch.sh']);ready();proofs=[]
 for index in (1,2):
  name='report-revision-immediate-refill-'+str(index)
  nested('/home/hong/deploy/comparison/venv/bin/python /root/test_reboot_guest.py prepare '+name)
  run(['python3',N/'reset_nested.py']);ready()
  nested('/home/hong/deploy/comparison/venv/bin/python /root/test_reboot_guest.py verify '+name,stdout=subprocess.DEVNULL)
  raw=subprocess.check_output([ssh,'cat '+str(F/'reboot-tests'/(name+'.json'))],text=True)
  proof=json.loads(raw);assert proof['success'] and proof['before_boot']!=proof['after_boot'];assert all(r['destroyed'] and r['file_verified'] for r in proof['sandboxes'])
  # Save verification evidence without printing per-process random challenge secrets.
  proofs.append(proof)
  print('verified isolated host reset and independent destruction',index,flush=True)
 (B/'nested-recovery.json').write_text(json.dumps({'host':'isolated nested Linux on 113','capacity':2,'purpose':'functional reboot validation, not formal startup benchmark','runs':proofs,'all_passed':True},indent=2))
 # Power off only the nested guest addressed by the private localhost SSH wrapper.
 pid=int((N/'qemu.pid').read_text())
 subprocess.run([ssh,'poweroff'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 deadline=time.monotonic()+60
 while pid and Path('/proc',str(pid)).exists() and time.monotonic()<deadline:time.sleep(1)
 if pid:assert not Path('/proc',str(pid)).exists(),'owned nested shutdown still pending'
 print('nested validation complete; physical host was not rebooted',flush=True)
