from pathlib import Path
import subprocess as sp
B=Path('/home/hong/src/research/report-revision-113');old=Path('/home/hong/src/research/startup-modes-113')
for name in ['prepare_native.py','complete_native.py']:
 s=(old/name).read_text().replace(str(old),str(B)).replace('/home/hong/src/research/ready-regression-113/tools',str(B/'tools')).replace("name = 'startup-'","name = 'revision-'")
 (B/name).write_text(s)
sp.run(['cp',str(old/'unseal'),str(B/'unseal')],check=True)
for product in ['kuasar-off','kuasar-uffd']:
 sp.run(['/home/hong/src/research/python-latest-113/venv/bin/python',str(B/'prepare_native.py'),product],check=True)
# complete_native's own source explicitly requires a surrounding lock.
import fcntl
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 sp.run(['/home/hong/src/research/python-latest-113/venv/bin/python',str(B/'complete_native.py')],check=True)
