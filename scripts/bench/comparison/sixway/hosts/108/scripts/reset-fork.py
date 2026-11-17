from pathlib import Path
import os,json,time,subprocess as sp,sys,shutil,urllib.request
mode='fork';capacity=64;P=Path('/opt/bench108/deploy/fork');D=Path('/opt/bench108/data/fork');unit='bench108-fork';seed='b108seed0001';port=18887
records=json.loads((D/'adapter-state.json').read_text()) if (D/'adapter-state.json').exists() else {}
assert all(r.get('pool_state') in ['ready','preparing','binding','quarantined'] for r in records.values()),'assigned sandbox must be preserved'
if sp.run(['systemctl','is-active','--quiet',unit]).returncode==0:
 req=urllib.request.Request(f'http://127.0.0.1:{port}/template-pool',data=b'{"drain":true}',headers={'X-API-Key':(P/'api-key').read_text().strip(),'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=180) as f:assert json.load(f)['owned']==0
 records={}
sp.run(['systemctl','stop',unit],check=True)
plugin='/opt/bench108/assets/cni/bridge'
for sid in [*records,seed]:
 sp.run([plugin],input=(P/'cni.json').read_text(),text=True,check=True,env={**os.environ,'CNI_COMMAND':'DEL','CNI_CONTAINERID':sid,'CNI_NETNS':'','CNI_IFNAME':'eth0','CNI_PATH':str(Path(plugin).parent)})
 name='kua-'+sid if sid!=seed else 'b108-fork-seed'
 if Path('/run/netns',name).exists():sp.run(['ip','netns','delete',name],check=True)
old=D/('old-state-'+str(time.time_ns()));old.mkdir()
for path in [D/'state',*D.glob('adapter-state.json*')]:
 if path.exists():path.rename(old/path.name)
(D/'state').mkdir();runtime=Path('/run/bench108-fork')
if runtime.exists():shutil.rmtree(runtime)
runtime.mkdir(mode=0o700)
p=Path('/etc/systemd/system/'+unit+'.service');s=p.read_text();import re
s=re.sub('E2B_TEMPLATE_POOL_SIZE=[0-9]+','E2B_TEMPLATE_POOL_SIZE='+str(capacity),s);p.write_text(s)
sp.run(['systemctl','daemon-reload'],check=True)
import secrets
(P/'api-key').write_text('e2b_'+secrets.token_hex(20));(P/'api-key').chmod(0o600)
if os.environ.get('POOL_RESET_STOPPED') != '1':sp.run(['systemctl','start',unit],check=True)
print('RESET',mode,capacity,flush=True)
