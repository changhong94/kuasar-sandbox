from pathlib import Path
import os,pwd,subprocess as sp,shutil
M=Path('/opt/bench108');A=M/'import113/comparison/assets';H=M/'data/agentenv';D=M/'deploy/agentenv';D.mkdir(parents=True,exist_ok=True)
assert os.geteuid()==0
user='bench108-agent'
try:pwd.getpwnam(user)
except KeyError:sp.run(['useradd','--system','--user-group','--home-dir',str(H),'--no-create-home','--shell','/usr/sbin/nologin',user],check=True)
sp.run(['usermod','-aG','kvm',user],check=True)
for ancestor in ['/home/huawei',str(M.parent),str(M),str(M/'data')]:sp.run(['setfacl','-m',f'u:{user}:rx',ancestor],check=True)
H.mkdir(exist_ok=True)
shutil.copytree(M/'assets/agentenv-deps',H/'deps',dirs_exist_ok=True)
shutil.copytree(A/'server-extracted/ublk',H/'ublk',dirs_exist_ok=True)
s=(A/'server-extracted/default.toml').read_text().replace('home_path = "/var/lib/aenv"',f'home_path = "{H}"').replace('mem_size_mib = 1024','mem_size_mib = 2048').replace('vcpu_count = 2','vcpu_count = 1').replace('allow_shrink = false','allow_shrink = true')
(H/'config').mkdir(exist_ok=True);(H/'config/config.toml').write_text(s)
sp.run(['chown','-R',f'{user}:{user}',str(H)],check=True)
sp.run(['setfacl','-m',f'u:{user}:rw','/dev/ublk-control'],check=True)
# Scoped mount supplies shipped OverlayBD default without replacing host settings.
for d in ['/etc/overlaybd']:
 Path(d).mkdir(exist_ok=True)
reg=(M/'import113/comparison/verify-image-server.py').read_text().replace('/home/hong/deploy/comparison/assets',str(A));(D/'registry.py').write_text(reg)
ns='b108-agent'
if not Path('/run/netns/'+ns).exists():sp.run(['ip','netns','add',ns],check=True)
sp.run(['ip','-n',ns,'link','set','lo','up'],check=True)
sp.run(['ip','netns','exec',ns,'sysctl','-qw','net.ipv4.ip_forward=1'],check=True)
unit=f'''[Unit]
Description=Six-way108 isolated AgentENV v0.2.4
[Service]
User={user}
Group={user}
SupplementaryGroups=kvm
NetworkNamespacePath=/run/netns/{ns}
Environment=API_ADDR=127.0.0.1:18000
Environment=AENV_CONFIG_PATH={H}/config/config.toml
Environment=AENV_DEPS_PATH={H}/deps
Environment=AENV_HOME_PATH={H}
Environment=AENV_RUNTIME_PATH=/run/bench108-agentenv
Environment=REGCTL_CONFIG={H}/config/regctl.json
Environment=PATH={M}/import113/comparison/tools:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
BindReadOnlyPaths={A}/server-extracted/etc/overlaybd:/etc/overlaybd
ExecStart={A}/server-extracted/server
RuntimeDirectory=bench108-agentenv
AmbientCapabilities=CAP_NET_ADMIN CAP_SYS_ADMIN
CapabilityBoundingSet=CAP_NET_ADMIN CAP_SYS_ADMIN
NoNewPrivileges=true
LimitNOFILE=1048576
LimitMEMLOCK=infinity
KillMode=mixed
TimeoutStopSec=60
'''
for name,body in [('bench108-agentenv',unit),('bench108-agent-registry',f'[Service]\nNetworkNamespacePath=/run/netns/{ns}\nExecStart=/usr/bin/python3 {D}/registry.py\n')]:
 (Path('/etc/systemd/system')/(name+'.service')).write_text(body)
sp.run(['systemctl','daemon-reload'],check=True);sp.run(['systemctl','start','bench108-agent-registry','bench108-agentenv'],check=True)
