from pathlib import Path
import os,json,shutil,subprocess as sp,time,hashlib,shlex
J=Path('/home/hong/codex-work/sevenway-fresh-181');R=Path('/srv/fork2');S=J/'f2rd-seed';B=J/'bin'
assert os.geteuid()==0
assert not R.exists(), 'Refuse to overwrite an existing fork2 deployment'
R.mkdir(mode=0o700);(R/'bin').mkdir();(R/'data').mkdir();(R/'app').mkdir()
img=R/'data.xfs';img.touch();os.truncate(img,256*1024**3)
sp.run(['mkfs.xfs','-q',str(img)],check=True);sp.run(['mount','-o','loop,noatime',str(img),str(R/'data')],check=True)
# Seed only immutable image publications, not old VM/sandbox state.
for name in ['store','publications','registry']:shutil.copytree(J/'fork2-seed/data'/name,R/'data'/name)
for name in ['base','cache','template-memory','prepared-artifacts']:(R/'data'/name).mkdir(mode=0o700)
for p in B.iterdir():
 if p.is_file() and p.name!='SHA256SUMS':shutil.copy2(p,R/'bin'/p.name)
for name in ['vmlinux','e2b-key-ctl','mkfs.erofs']:shutil.copy2(J/'fork2-seed/bin'/name,R/'bin'/name)
shutil.copy2('/home/hong/src/research/kuasar-native-fork/cloud-hypervisor/target/release/cloud-hypervisor',R/'bin/cloud-hypervisor')
shutil.copy2('/home/hong/src/research/kuasar-native-fork/kuasar-sandbox/guest-runtime/bin/x86_64/sandbox-runtime.bundle',R/'bin/sandbox-runtime.bundle')
for p in (S/'app').iterdir():
 if p.is_file():(R/'app'/p.name).write_text(p.read_text().replace('f2rd','fork2').replace('/home/huawei/','/home/hong/'))
for name in ['conductor.json','console.json','manifest.json','proxy.json','store.json','cache.yaml','service.env']:
 p=R/name;p.write_text((S/name).read_text().replace('f2rd','fork2').replace('/home/huawei/','/home/hong/'));p.chmod(0o600)
c=json.loads((R/'conductor.json').read_text());c['image_template_catalogs']=[];c['sandbox']['boot']['runtime']=str(R/'bin/sandbox-runtime.bundle')
for pool in c['units']['runner_pools']:
 if pool.get('prepared_vm'):pool['size']=64;pool['prepare_concurrency']=8;pool['prepared_restore']=False  # bootstrap images until idle catalogs are prepared and atomically activated
 else:pool['size']=0
c['sandbox']['resources']['capacity']['cpu']=2;c['sandbox']['resources']['allocatable']['cpu']=2
(R/'conductor.json').write_text(json.dumps(c,indent=2))
h=hashlib.sha256((R/'bin/sandbox-ctl').read_bytes()).hexdigest()
for p in (S/'f2rd-units').glob('*.service'):
 name=p.name.replace('f2rd','fork2');dst=Path('/etc/systemd/system')/name;assert not dst.exists(),dst
 s=p.read_text().replace('f2rd','fork2').replace('/home/huawei/','/home/hong/').replace('--ports=8','--ports=320')
 import re
 s=re.sub(r'KUASAR_EMBEDDED_SANDBOX_SHA256=[0-9a-f]+','KUASAR_EMBEDDED_SANDBOX_SHA256='+h,s)
 dst.write_text(s)
Path('/etc/systemd/system/sandbox-runner.slice').write_text('[Unit]\nDescription=Owned sandbox benchmark runners\n[Slice]\n')
sp.run(['systemctl','daemon-reload'],check=True)
sp.run(['systemctl','start','fork2-store','fork2-cache','fork2-switch','fork2-shared','fork2-conductor','fork2-proxy'],check=True)
for i in range(200):
 if Path('/run/fork2/node.sock').exists():break
 time.sleep(.1)
env=os.environ.copy()
for line in (R/'service.env').read_text().splitlines():
 if line and not line.startswith('#')and '='in line:k,v=line.split('=',1);env[k]=' '.join(shlex.split(v))
sp.run([str(R/'bin/node-ctl'),'manifest-key','add','--socket','/run/fork2/node.sock'],env=env,check=True,stdout=sp.DEVNULL)
(R/'bin/python-sdk').write_text('#!/bin/bash\nexec /home/hong/codex-work/remote-path-108/venv/bin/python "$@"\n');(R/'bin/python-sdk').chmod(0o755)
(J/'fork2-build-provenance.json').write_text(json.dumps({'host':'181','runtime_rebuilt':True,'pools':c['units']['runner_pools'],'binaries':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in (R/'bin').iterdir()if p.is_file()}},indent=2))
print('FORK2_DEPLOYED_CURRENT_SOURCE',flush=True)

# Shared template RAM cache is private; restore validates permissions.
(R/"data/template-memory").mkdir(parents=True,exist_ok=True)
(R/"data/template-memory").chmod(0o700)
