from pathlib import Path
import os,sys,time,json,shutil,subprocess as sp
M=Path('/opt/bench108');R=M/'results/restore-exec-opt-108';P=M/'deploy/fork';D=M/'data/fork';mode=sys.argv[1]
sp.run(['env','POOL_RESET_STOPPED=1',str(M/'venv/bin/python'),str(M/'scripts/reset-fork.py')],check=True)
old=D/('retired-restore-exec-templates-'+str(time.time_ns()));(D/'snapshot-templates').rename(old);(D/'snapshot-templates').mkdir()
if mode=='baseline':
 shutil.copyfile(P/'bin/cloud-hypervisor',R/'before/cloud-hypervisor')
 runtime=M/'assets/fork-runtime-metadata-opt.ext4';assert not runtime.exists()
 sp.run(['cp','--reflink=auto','--sparse=always',str(M/'assets/fork-runtime-tcp-template-opt.ext4'),str(runtime)],check=True);runtime.chmod(0o600)
 for c in ['write /opt/bench108/build/image-metadata /usr/bin/image-metadata','set_inode_field /usr/bin/image-metadata mode 0100755']:
  sp.run(['debugfs','-w','-R',c,str(runtime)],check=True)
 sp.run(['e2fsck','-fn',str(runtime)],check=True);runtime.chmod(0o444)
 with runtime.open('rb') as f:os.fsync(f.fileno())
 p=P/'config.toml';s=p.read_text();assert 'fork-runtime-tcp-template-opt.ext4' in s;p.write_text(s.replace('fork-runtime-tcp-template-opt.ext4','fork-runtime-metadata-opt.ext4'))
 with p.open('rb') as f:os.fsync(f.fileno())
 new=P/'bin/cloud-hypervisor.next';shutil.copyfile(M/'build/snapshot-ch/release/cloud-hypervisor',new);new.chmod(0o755)
 with new.open('rb') as f:os.fsync(f.fileno())
 new.replace(P/'bin/cloud-hypervisor')
unit=Path('/etc/systemd/system/bench108-fork.service.d/restore-exec-opt.conf')
unit.write_text('[Service]\nEnvironment=CH_RESTORE_TIMING=1\nEnvironment=E2B_TEMPLATE_METADATA='+('0' if mode=='baseline' else '1')+'\n')
sp.run(['systemctl','daemon-reload'],check=True)
start=time.perf_counter_ns();sp.run(['systemctl','start','bench108-fork'],check=True)
z=sp.run([str(M/'venv/bin/python'),str(M/'tools/fork-opt3-108/wait-ready.py')],capture_output=True,text=True,check=True)
(R/(mode+'-deploy.json')).write_text(json.dumps({'service_start_to_ready_ms':(time.perf_counter_ns()-start)/1e6,'ready':json.loads(z.stdout),'retired_templates':str(old)},indent=2))
shutil.copyfile(D/'adapter-state.json.snapshot-preparation.json',R/(mode+'-preparation.json'));print(z.stdout)
