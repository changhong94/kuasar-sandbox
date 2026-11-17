import os,subprocess as sp,time,json,shutil
from pathlib import Path
M=Path('/opt/bench108');R=M/'results/identity-opt-108';P=M/'deploy/fork';D=M/'data/fork'
# Invoked inside b108-fork network namespace. Drain and stop only owned service.
sp.run(['env','POOL_RESET_STOPPED=1',str(M/'venv/bin/python'),str(M/'scripts/reset-fork.py')],check=True)
shutil.copyfile(P/'bin/sandboxer',R/'before/sandboxer')
old=D/('retired-identity-templates-'+str(time.time_ns()));(D/'snapshot-templates').rename(old);(D/'snapshot-templates').mkdir()
runtime=M/'assets/fork-runtime-identity-opt.ext4';assert not runtime.exists()
sp.run(['cp','--reflink=auto','--sparse=always',str(M/'assets/fork-runtime-python-stream.ext4'),str(runtime)],check=True);runtime.chmod(0o600)
for command in ['rm /usr/bin/vmm-task','write /opt/bench108/build/snapshot-pool/release/vmm-task /usr/bin/vmm-task','set_inode_field /usr/bin/vmm-task mode 0100755']:
 sp.run(['debugfs','-w','-R',command,str(runtime)],check=True)
sp.run(['e2fsck','-fn',str(runtime)],check=True)
runtime.chmod(0o444)
with runtime.open('rb') as f:os.fsync(f.fileno())
new=P/'bin/sandboxer.next';shutil.copyfile(M/'build/snapshot-pool/release/cloud_hypervisor',new);new.chmod(0o755)
with new.open('rb') as f:os.fsync(f.fileno())
new.replace(P/'bin/sandboxer')
p=P/'config.toml';s=p.read_text();assert 'fork-runtime-python-stream.ext4' in s;p.write_text(s.replace('fork-runtime-python-stream.ext4','fork-runtime-identity-opt.ext4'))
with p.open('rb') as f:os.fsync(f.fileno())
start=time.perf_counter_ns();sp.run(['systemctl','start','bench108-fork'],check=True)
z=sp.run([str(M/'venv/bin/python'),str(M/'tools/fork-opt3-108/wait-ready.py')],capture_output=True,text=True,check=True)
(R/'deploy.json').write_text(json.dumps({'old_templates':str(old),'service_start_to_ready_ms':(time.perf_counter_ns()-start)/1e6,'ready':json.loads(z.stdout)},indent=2));print(z.stdout)
