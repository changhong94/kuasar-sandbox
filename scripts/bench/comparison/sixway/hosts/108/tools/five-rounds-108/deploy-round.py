from pathlib import Path
import os,sys,time,json,shutil,subprocess as sp,re,hashlib
M=Path('/opt/bench108');n=sys.argv[1];R=M/'results/five-rounds-108'/('round'+n);P=M/'deploy/fork';D=M/'data/fork';spec=json.loads((R/'deploy-spec.json').read_text())
sp.run(['env','POOL_RESET_STOPPED=1',str(M/'venv/bin/python'),str(M/'scripts/reset-fork.py')],check=True)
old=D/('retired-five-round'+n+'-'+str(time.time_ns()));(D/'snapshot-templates').rename(old);(D/'snapshot-templates').mkdir()
config=P/'config.toml';cfg=config.read_text();old_runtime=re.search(r'image_path="([^"]+)"',cfg).group(1)
if spec.get('runtime'):
 assert Path(spec['runtime']).is_file()
 cfg=cfg.replace(old_runtime,spec['runtime']);config.write_text(cfg)
 with config.open('rb') as f:os.fsync(f.fileno())
 old_runtime=spec['runtime']
if spec.get('guest'):
 runtime=M/'assets'/('fork-runtime-five-round'+n+'.ext4');assert not runtime.exists()
 sp.run(['cp','--reflink=auto','--sparse=always',old_runtime,str(runtime)],check=True);runtime.chmod(0o600)
 for c in ['rm /usr/bin/vmm-task','write /opt/bench108/build/snapshot-pool/release/vmm-task /usr/bin/vmm-task','set_inode_field /usr/bin/vmm-task mode 0100755']:
  sp.run(['debugfs','-w','-R',c,str(runtime)],check=True)
 sp.run(['e2fsck','-fn',str(runtime)],check=True);runtime.chmod(0o444)
 with runtime.open('rb') as f:os.fsync(f.fileno())
 cfg=cfg.replace(old_runtime,str(runtime));config.write_text(cfg)
 with config.open('rb') as f:os.fsync(f.fileno())
for key,dest,source in [('host','sandboxer',M/'build/snapshot-pool/release/cloud_hypervisor'),('ch','cloud-hypervisor',M/'build/snapshot-ch/release/cloud-hypervisor')]:
 if spec.get(key):
  source=Path(spec.get(key+'_source',source))
  shutil.copyfile(P/'bin'/dest,R/'before'/dest)
  new=P/'bin'/(dest+'.next');shutil.copyfile(source,new);new.chmod(0o755)
  with new.open('rb') as f:os.fsync(f.fileno())
  new.replace(P/'bin'/dest)
sp.run(['systemctl','daemon-reload'],check=True);start=time.perf_counter_ns();sp.run(['systemctl','start','bench108-fork'],check=True)
z=sp.run([str(M/'venv/bin/python'),str(M/'tools/fork-opt3-108/wait-ready.py')],capture_output=True,text=True,check=True)
(R/'deploy.json').write_text(json.dumps({'service_start_to_ready_ms':(time.perf_counter_ns()-start)/1e6,'ready':json.loads(z.stdout),'retired_templates':str(old),'spec':spec},indent=2));shutil.copyfile(D/'adapter-state.json.snapshot-preparation.json',R/'preparation.json');print(z.stdout)
