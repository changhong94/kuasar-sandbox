#!/usr/bin/env python3
"""Install a separate native demo on 108. Refuses to overwrite an existing deployment."""
import argparse,json,os,pathlib,shutil,socket,subprocess,hashlib
p=argparse.ArgumentParser();p.add_argument('--binaries',required=True);a=p.parse_args();src=pathlib.Path(a.binaries);root=pathlib.Path('/srv/fork2');assert os.geteuid()==0;assert not root.exists()
for port in (19210,19211,19212):
 with socket.socket() as s:s.bind(('0.0.0.0',port))
assert not pathlib.Path('/run/netns/fork2sw-ns').exists()
assert not subprocess.check_output(['ip','route','show','exact','100.128.0.0/19']).strip()
root.mkdir(mode=0o700);data=root/'data';data.mkdir(mode=0o700);
volume=root/'data.xfs'
with volume.open('wb') as f:f.truncate(64*1024**3)
subprocess.run(['mkfs.xfs','-q','-f',str(volume)],check=True)
subprocess.run(['mount','-o','loop',str(volume),str(data)],check=True)
b=root/'bin';b.mkdir();app=root/'app';shutil.copytree(pathlib.Path(__file__).parent,app)
for name in ('node-ctl','sandbox-ctl','connector-ctl','store-ctl','manifest-ctl','flatten-ctl','e2b-key-ctl','cloud-hypervisor','vmlinux','sandbox-runtime.bundle'):
 shutil.copy2(src/name,b/name)
shutil.copy2('/home/huawei/src/research/kuasar-native-fork/tools/mkfs.erofs',b/'mkfs.erofs')
# Deployment-owned immutable kernel: compute once, retain identity validation at claim.
identity=b/'vmlinux.sha256'
identity.write_text(hashlib.sha256((b/'vmlinux').read_bytes()).hexdigest()+'  vmlinux\n')
identity.chmod(0o444)
with identity.open('rb') as f:os.fsync(f.fileno())
for name in ('base','registry','publications'):(data/name).mkdir(mode=0o700)
def save(name,obj):
 path=root/name;path.write_text(json.dumps(obj,indent=2));path.chmod(0o600);return path
def run(args,**kw):return subprocess.run(list(map(str,args)),check=True,**kw)
env={**os.environ,'MANIFEST_KEY':os.urandom(32).hex(),'PATH':str(b)+':'+os.environ['PATH']}
env['API_SECRET']=subprocess.check_output([b/'e2b-key-ctl','derive-api-secret'],env=env,text=True).strip();key=subprocess.check_output([b/'e2b-key-ctl','gen-apikey'],env=env,text=True).strip()
f=root/'service.env';f.write_text('MANIFEST_KEY='+env['MANIFEST_KEY']+'\nAPI_SECRET='+env['API_SECRET']+'\nPATH='+env['PATH']+'\n');f.chmod(0o600)
store=save('store.json',{'listen':'127.0.0.1:19212','backend':'fs','fs':{'root':str(data/'store'),'verify_content_key':True}});run([b/'store-ctl','init','--config',store,'--generation','G1'],capture_output=True)
manifest=save('manifest.json',{'manifest':{'verify_content':True,'write_generation':'G1'},'store':{'endpoint':'127.0.0.1:19212','pool':4,'timeout':'30s'},'cache':{'endpoint':''},'chunker':{'mode':'cdc'},'crypto':{'chunk':'aes','manifest':'aes'}})
r='/run/fork2';unit='fork2-runner@.service'
cfg={'api':{'domain':'native.local','listen':'127.0.0.1:19210'},'proxy':{'auth':'enforce'},'encryption_key':os.urandom(32).hex(),'manifest_config':str(manifest),'paths':{'run_root':r,'base_root':str(data/'base'),'config_socket':r+'/node.sock'},'units':{'install':False,'runner_pools':[{'unit':unit,'size':2,'prepared_vm':True,'name':'prepared','priority':100},{'unit':unit,'size':2,'name':'cold'}],'builder_pools':[{'unit':'fork2-builder@.service','size':0}]},'sandbox':{'private_ram_fork':True,'timeout_sec':86400,'resources':{'capacity':{'cpu':2,'memory':'2GiB'},'allocatable':{'cpu':2,'memory':'2GiB'}},'network':{'switch':'fork2sw','tapfd_socket':r+'/tapfd.sock','bare':{'inner_ip':'169.254.1.1/31','nexthop':'169.254.1.0'},'e2b':{'inner_ip':'169.254.0.21/30','nexthop':'169.254.0.22'}},'boot':{'kernel':str(b/'vmlinux'),'runtime':str(b/'sandbox-runtime.bundle'),'overlay_diff_template':'mkfs://ext4?size=8GiB'}},'checkpoint':{'mode':'local','remote':{'ref_location_parent':(data/'publications').as_uri()}}};save('conductor.json',cfg)
save('proxy.json',{'config_socket':r+'/node.sock','paths':{'run_root':r+'/proxy'},'data_listen':'127.0.0.1:19211','stats_socket':r+'/proxy-stats.sock','shm_path':r+'/routes.shm','route_capacity':64,'workers':1,'auth':'enforce','park_timeout':'30s'})
save('console.json',{'api':'http://127.0.0.1:19210','key':key})
def service(name,text):
 path=pathlib.Path('/etc/systemd/system')/name
 with path.open('x') as f:f.write(text)
service('srv-fork2-data.mount',f'[Unit]\nDescription=Dedicated fork2 data volume\n[Mount]\nWhat={volume}\nWhere={data}\nType=xfs\nOptions=loop\n[Install]\nWantedBy=local-fs.target\n')
service(unit,f'[Unit]\nCollectMode=inactive-or-failed\n[Service]\nType=exec\nWorkingDirectory={r}\nEnvironmentFile={root}/service.env\nExecStart={b}/node-ctl run-sandbox --pidfile={r}/runners/%i.pid --config-socket={r}/node.sock --run-id=%i\nRestart=no\nKillMode=control-group\nTimeoutStopSec=30\nSlice=sandbox-runner.slice\nDelegate=yes\n')
commands={
 'store':f'{b}/store-ctl serve --config {root}/store.json',
 'switch':f'{b}/connector-ctl vswitch serve fork2sw --netns=fork2sw-ns --ports=8 --mac-addr=02:00:00:09:02:01 --port-mac-addr=per-port --floating-ip-base=100.128.0.0 --mode=tap --mgmt-extract=:fork2sw-m0:169.254.169.252,0.0.0.0/0 --tapfd-listen={r}/tapfd.sock --watch-interval=2s',
 'conductor':f'{b}/node-ctl conductor serve --config {root}/conductor.json',
 'proxy':f'{b}/node-ctl proxy serve --config {root}/proxy.json'}
for name,command in commands.items():
 after='network.target' if name in ('store','switch') else ('fork2-store.service fork2-switch.service' if name=='conductor' else 'fork2-conductor.service')
 extra=''
 if name=='switch':extra=f'ExecStartPre=/usr/bin/python3 {app}/network.py prepare\nExecStartPost=/usr/bin/python3 {app}/network.py route\n'
 service('fork2-'+name+'.service',f'[Unit]\nDescription=Dedicated fork2 benchmark {name}\nRequiresMountsFor={data}\nAfter={after}\n[Service]\nType=simple\nEnvironmentFile={root}/service.env\nEnvironment=FORKLAB_ROOT={root}\n{extra}ExecStart={command}\nRestart=on-failure\nRestartSec=2\nTimeoutStopSec=30\n[Install]\nWantedBy=multi-user.target\n')
run(['systemctl','daemon-reload']);run(['systemctl','enable','srv-fork2-data.mount']);run(['systemctl','enable','--now','fork2-store.service','fork2-switch.service'])
run(['systemctl','enable','--now','fork2-conductor.service'])
import time
for _ in range(300):
 if pathlib.Path(r+'/node.sock').exists():break
 time.sleep(.1)
else:raise TimeoutError('conductor')
run([b/'node-ctl','manifest-key','add','--socket',r+'/node.sock'],env=env,capture_output=True)
run(['systemctl','enable','--now','fork2-proxy.service'])
print('fork2 native benchmark API deployed on loopback 19210; existing services untouched')
