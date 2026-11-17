from pathlib import Path
import os,time,json,shutil,subprocess as sp
M=Path('/opt/bench108');R=M/'results/five-rounds-108/round1';P=M/'deploy/fork';D=M/'data/fork'
sp.run(['env','POOL_RESET_STOPPED=1',str(M/'venv/bin/python'),str(M/'scripts/reset-fork.py')],check=True)
old=D/('retired-five-round1-'+str(time.time_ns()));(D/'snapshot-templates').rename(old);(D/'snapshot-templates').mkdir()
runtime=M/'assets/fork-runtime-uniform-cache.ext4';assert not runtime.exists()
sp.run(['cp','--reflink=auto','--sparse=always',str(M/'assets/fork-runtime-metadata-opt.ext4'),str(runtime)],check=True);runtime.chmod(0o600)
for c in ['rm /usr/bin/image-metadata','write /opt/bench108/build/image-metadata /usr/bin/image-metadata','set_inode_field /usr/bin/image-metadata mode 0100755']:
 sp.run(['debugfs','-w','-R',c,str(runtime)],check=True)
sp.run(['e2fsck','-fn',str(runtime)],check=True);runtime.chmod(0o444)
with runtime.open('rb') as f:os.fsync(f.fileno())
p=P/'config.toml';s=p.read_text();assert 'fork-runtime-metadata-opt.ext4' in s;p.write_text(s.replace('fork-runtime-metadata-opt.ext4','fork-runtime-uniform-cache.ext4'))
with p.open('rb') as f:os.fsync(f.fileno())
# Reject the synchronous-backend experiment; restore the tested prior host.
new=P/'bin/sandboxer.next';shutil.copyfile(M/'results/restore-exec-sync-108/before/sandboxer',new);new.chmod(0o755)
with new.open('rb') as f:os.fsync(f.fileno())
new.replace(P/'bin/sandboxer')
Path('/etc/systemd/system/bench108-fork.service.d/restore-exec-opt.conf').write_text('[Service]\nEnvironment=CH_RESTORE_TIMING=1\nEnvironment=E2B_TEMPLATE_METADATA=1\nEnvironment=E2B_TEMPLATE_READ_CACHE_BYTES=536870912\n')
sp.run(['systemctl','daemon-reload'],check=True);start=time.perf_counter_ns();sp.run(['systemctl','start','bench108-fork'],check=True)
z=sp.run([str(M/'venv/bin/python'),str(M/'tools/fork-opt3-108/wait-ready.py')],capture_output=True,text=True,check=True)
(R/'deploy.json').write_text(json.dumps({'service_start_to_ready_ms':(time.perf_counter_ns()-start)/1e6,'ready':json.loads(z.stdout),'retired_templates':str(old)},indent=2));shutil.copyfile(D/'adapter-state.json.snapshot-preparation.json',R/'preparation.json');print(z.stdout)
