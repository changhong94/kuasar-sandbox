from pathlib import Path
import subprocess as s,shutil,hashlib,json
r=Path('/home/hong/src/research/startup-latest-20261126');base=Path('/srv/fork2')
assert s.run(['systemctl','is-active','--quiet','fork2-conductor']).returncode!=0
backup=r/'original-bin';backup.mkdir(exist_ok=False)
for p in (r/'bin').iterdir():
 target=base/'bin'/p.name
 if target.exists():shutil.copy2(target,backup/p.name)
 shutil.copy2(p,target)
h=hashlib.sha256((base/'bin/sandbox-ctl').read_bytes()).hexdigest()
for unit in ['fork2-runner@','fork2-shared-controller']:
 d=Path('/etc/systemd/system')/(unit+'.service.d');d.mkdir(exist_ok=True)
 (d/'zzzzzz-latest-20261126.conf').write_text('[Service]\nEnvironment=KUASAR_EMBEDDED_SANDBOX_SHA256='+h+'\n')
s.run(['systemctl','daemon-reload'],check=True)
s.run(['systemctl','start','fork2-store','fork2-switch'],check=True)
s.run(['systemctl','start','fork2-conductor','fork2-proxy'],check=True)
print('started',flush=True)
