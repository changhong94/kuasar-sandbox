import subprocess as sp,pwd
from pathlib import Path
M=Path('/opt/bench108');D=M/'deploy/mlink-lang';D.mkdir(exist_ok=False)
user='bench108-mlink-lang'
try:pwd.getpwnam(user)
except KeyError:sp.run(['useradd','--system','--user-group','--no-create-home','--shell','/usr/sbin/nologin',user],check=True)
sp.run(['setfacl','-m',f'u:{user}:rx','/home/huawei'],check=True)
for name in ['mlink-private-start.sh','mlink-env.sh','mlink-dev.py']:
 s=(M/'deploy/mlink'/name).read_text().replace('bench108-mlink','bench108-mlink-lang').replace('b108-mlink','b108-mlink-lang').replace('/deploy/mlink','/deploy/mlink-lang').replace('/data/mlink','/data/mlink-lang')
 (D/name).write_text(s)
(D/'bin').symlink_to(M/'deploy/mlink/bin',target_is_directory=True)
sp.run(['ip','netns','add','b108-mlink-lang'],check=True);sp.run(['ip','-n','b108-mlink-lang','link','set','lo','up'],check=True)
Path('/etc/systemd/system/bench108-mlink-lang.service').write_text('''[Unit]
Description=Isolated Node/Ruby matched benchmark mlink
[Service]
Type=simple
NetworkNamespacePath=/run/netns/b108-mlink-lang
PrivateMounts=yes
TemporaryFileSystem=/run/netns
TemporaryFileSystem=/run/tt
ExecStart=/bin/bash /opt/bench108/deploy/mlink-lang/mlink-private-start.sh
KillMode=mixed
TimeoutStopSec=80
LimitNOFILE=1048576
LimitMEMLOCK=infinity
''')
sp.run(['systemctl','daemon-reload'],check=True);sp.run(['systemctl','start','bench108-mlink-lang'],check=True)
