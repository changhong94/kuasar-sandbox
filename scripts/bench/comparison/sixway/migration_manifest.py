from pathlib import Path
import json,subprocess as sp,hashlib,sys
base=Path('/home/hong/src/research');r=Path(sys.argv[1]);out={}
for name in ['sandbox_fork/cloud-hypervisor/cloud-hypervisor','sandbox_fork/kuasar-io/kuasar','sandbox_bench/src/kuasar-fork/kuasar-io/kuasar']:
 p=base/name
 def git(*a):return sp.check_output(['git','-c','safe.directory='+str(p),'-C',str(p),*a],text=True)
 out[name]={'head':git('rev-parse','HEAD').strip(),'branch':git('branch','--show-current').strip(),'status':git('status','--porcelain'),'diff_sha256':hashlib.sha256(git('diff','HEAD').encode()).hexdigest()}
files={}
for name in ['bin/sandboxer','bin/cloud-hypervisor','config.toml','cni.json','supervisor.py']:
 p=Path('/home/hong/deploy/kuasar-fork-research')/name;files[str(p)]={'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()}
for name in ['rootfs.ext4','boot.cpio','vmlinuz']:
 p=Path('/home/hong/data/kuasar-fork/guest')/name;files[str(p)]={'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()}
for name in ['vmm/sandbox/src/cloud_hypervisor/mod.rs','vmm/sandbox/src/network/link.rs','vmm/sandbox/src/network/mod.rs','integrations/e2b/server.py']:
 p=base/'sandbox_fork/kuasar-io/kuasar'/name;files[str(p)]={'bytes':p.stat().st_size,'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest()}
(r/'migration-manifest.json').write_text(json.dumps({'source_root':'/home/huawei/src/research','target_root':str(base),'copied':['sandbox_fork','sandbox_bench'],'source_preserved':True,'exclusions':['target/','node_modules/','__pycache__/','sandbox_bench/deploy/agentenv/run/'],'old_venvs':'Historical absolute symlinks preserved, not used; six-way uses existing /home/hong/deploy/comparison/venv SDK 2.25.1','repositories':out,'files':files,'host_kernel':sp.check_output(['uname','-a'],text=True).strip(),'matched_image':json.loads(Path('/home/hong/deploy/kuasar-fork-research/image-identity.json').read_text())['base_manifest_digest']},indent=2))
