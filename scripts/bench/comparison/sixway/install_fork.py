from pathlib import Path
import subprocess as sp,shutil,json,secrets,os
H=Path('/home/hong');B=H/'src/research/sandbox_bench';Q=H/'src/research/sandbox_fork/kuasar-io/kuasar';P=H/'deploy/kuasar-fork-research';DATA=H/'data/kuasar-fork'
if sp.run(['systemctl','is-active','--quiet','bench-kuasar-fork']).returncode==0:
 raise SystemExit('Stop bench-kuasar-fork and verify owned instances are gone before reinstalling binaries.')
P.mkdir(parents=True,exist_ok=True);DATA.mkdir(parents=True,exist_ok=True)
for d in ['bin','empty-containerd','state']:(P/d).mkdir(exist_ok=True)
for d in ['guest','ipam','state']:(DATA/d).mkdir(exist_ok=True)
for name in ['sandboxer','cloud-hypervisor']:
 src=B/('deploy/sixway-113/bin' if name=='sandboxer' else 'deploy/e2b-deferred-network/bin')/name
 shutil.copy2(src,P/'bin'/name)
matched=P/'matched-image-build/rootfs.ext4'
if not matched.is_file():raise SystemExit('Run build_matched_guest.py first to reuse the exact five-way OCI fixture.')
for name in ['rootfs.ext4','boot.cpio']:
 src=matched if name=='rootfs.ext4' else B/'deploy/e2b-deferred-network/guest'/name
 if not (DATA/'guest'/name).exists():sp.run(['cp','--reflink=auto',str(src),str(DATA/'guest'/name)],check=True)
shutil.copy2(P/'matched-image-build/image-identity.json',P/'image-identity.json')
shutil.copy2(B/'deploy/common/vmlinuz-6.8',DATA/'guest/vmlinuz')
cfg=(B/'deploy/e2b-deferred-network/fork/config.toml').read_text().replace('/opt/sbb-sdk','/opt/sbb-six').replace('vcpus=2','vcpus=1').replace('memory_in_mb=512','memory_in_mb=2048')
cfg=cfg.replace('/home/huawei/src/research/sandbox_bench/deploy/common/vmlinuz-6.8',str(DATA/'guest/vmlinuz')).replace('/opt/sbb-six/guest/',str(DATA/'guest')+'/')
(P/'config.toml').write_text(cfg)
(P/'cni.json').write_text(json.dumps({'cniVersion':'1.0.0','name':'sixway-fork','type':'bridge','bridge':'sixforkbr0','isGateway':True,'ipMasq':False,'ipam':{'type':'host-local','dataDir':str(DATA/'ipam'),'subnet':'10.76.0.0/16','routes':[{'dst':'0.0.0.0/0'}]}}))
if not (P/'api-key').exists():(P/'api-key').write_text("e2b_"+secrets.token_hex(20))
(P/'api-key').chmod(0o600)
sp.run(['mkdir','-p','/opt/sbb-six'],check=True)
if not os.path.ismount('/opt/sbb-six'):sp.run(['mount','--bind',str(P),'/opt/sbb-six'],check=True)
if not Path('/run/netns/bench113-fork').exists():sp.run(['ip','netns','add','bench113-fork'],check=True)
sp.run(['ip','netns','exec','bench113-fork','ip','link','set','lo','up'],check=True)
(P/'supervisor.py').write_text('''import sys,subprocess as sp,json,os,time,signal
from pathlib import Path
P=Path('/home/hong/deploy/kuasar-fork-research');DATA=Path('/home/hong/data/kuasar-fork');B=Path('/home/hong/src/research/sandbox_bench');Q=Path('/home/hong/src/research/sandbox_fork/kuasar-io/kuasar')
sys.path.insert(0,str(Q/'integrations/e2b'));import vm_rpc
children=[]
def stop(*args):
 for p in reversed(children):
  if p.poll() is None:p.terminate()
 sys.exit(0)
signal.signal(signal.SIGTERM,stop)
env={**os.environ,'KUASAR_CONTAINERD_TTRPC_ADDRESS':str(P/'unused-containerd.sock.ttrpc')}
cmd='mount --bind /home/hong/deploy/kuasar-fork-research/empty-containerd /run/containerd; exec /opt/sbb-six/bin/sandboxer --config /opt/sbb-six/config.toml --dir /home/hong/data/kuasar-fork/state --listen /opt/sbb-six/sandboxer.sock --admin-listen /opt/sbb-six/admin.sock'
children.append(sp.Popen(['unshare','--mount','--propagation','private','bash','-ec',cmd],env=env))
for i in range(200):
 try:vm_rpc.admin(P/'admin.sock','sandbox-list');break
 except Exception:
  if children[0].poll() is not None:raise RuntimeError('sandboxer exited')
  time.sleep(.05)
else:raise RuntimeError('sandboxer timeout')
sid='sixwayseed00001';name='sixway-fork-seed'
if not Path('/run/netns/'+name).exists():sp.run(['ip','netns','add',name],check=True)
holder=sp.Popen(['ip','netns','exec',name,'sleep','infinity']);children.append(holder)
ns='/proc/'+str(holder.pid)+'/ns/net';wanted=os.stat('/run/netns/'+name).st_ino
for i in range(1000):
 if os.stat(ns).st_ino==wanted:break
 time.sleep(.001)
else:raise RuntimeError('seed namespace holder timeout')
cni=json.loads((P/'cni.json').read_text());ce={**os.environ,'CNI_COMMAND':'ADD','CNI_CONTAINERID':sid,'CNI_NETNS':ns,'CNI_IFNAME':'eth0','CNI_PATH':str(B/'tools/cni')}
z=sp.run([str(B/'tools/cni/bridge')],input=json.dumps(cni),text=True,capture_output=True,env=ce,check=True)
(P/'seed-cni-result.json').write_text(z.stdout)
t=time.monotonic();info=vm_rpc.admin(P/'admin.sock','sandbox-boot',sandbox_id=sid,netns=ns)
(P/'seed-preparation.json').write_text(json.dumps({'boot_ms':(time.monotonic()-t)*1000,'pid':info['live_fork']['pid'],'prefetch':False,'cpu':1,'memory_mib':2048}))
children.append(sp.Popen(['python3',str(Q/'integrations/e2b/server.py'),'--listen','127.0.0.1','--port','18884','--source',sid,'--api-key-file',str(P/'api-key'),'--state',str(DATA/'adapter-state.json'),'--admin-socket',str(P/'admin.sock'),'--sandbox-state',str(DATA/'state'),'--cni-bin',str(B/'tools/cni'),'--cni-config',str(P/'cni.json'),'--cpu-count','1','--memory-mb','2048']))
while True:
 for p in children:
  if p.poll() is not None:raise RuntimeError('owned service exited: '+str(p.args))
 time.sleep(1)
''')
unit='''[Unit]
Description=Six-way Kuasar fork research backend
After=network.target
[Service]
Type=simple
NetworkNamespacePath=/run/netns/bench113-fork
ExecStart=/usr/bin/python3 /home/hong/deploy/kuasar-fork-research/supervisor.py
KillMode=control-group
TimeoutStopSec=20
LimitNOFILE=65536
[Install]
WantedBy=multi-user.target
'''
Path('/etc/systemd/system/bench-kuasar-fork.service').write_text(unit)
sp.run(['systemctl','daemon-reload'],check=True)
print('deployment installed; not started')
