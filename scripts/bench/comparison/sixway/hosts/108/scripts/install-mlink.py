from pathlib import Path
import subprocess as sp,pwd,os
M=Path('/home/huawei/src/research/sixway_startup_108');D=M/'deploy/mlink';R=M/'src/kuasar-mlink/private/kuasar-mlink';user='bench108-mlink'
assert os.geteuid()==0
try:pwd.getpwnam(user)
except KeyError:sp.run(['useradd','--system','--user-group','--no-create-home','--shell','/usr/sbin/nologin',user],check=True)
sp.run(['setfacl','-m',f'u:{user}:rx','/home/huawei'],check=True)
replacements={'/home/hong/src/private/kuasar-mlink':str(R),'/opt/bench-private-mlink':str(M/'assets/mlink-opt'),'/home/hong/deploy/private-pilot':str(D),'/home/hong/data/mlink/client.json':str(M/'data/mlink/client.json'),'/home/hong/data/mlink3':str(M/'data/mlink'),'bench113-m':'b108-mlink','bench-mlink-io':user,'/usr/local/libexec/bench113-ublk-owner':str(M/'import113/comparison/ublk-owner')}
for p in D.iterdir():
 if p.suffix not in ('.sh','.py'):continue
 s=p.read_text()
 for a,b in replacements.items():s=s.replace(a,b)
 s=s.replace('restorecon /run;', '').replace('restorecon /run/netns;', '').replace('restorecon -R /dev','true')
 p.write_text(s)
ns='b108-mlink'
if not Path('/run/netns/'+ns).exists():sp.run(['ip','netns','add',ns],check=True)
sp.run(['ip','-n',ns,'link','set','lo','up'],check=True)
Path('/etc/systemd/system/bench108-mlink.service').write_text(f'''[Unit]
Description=Six-way108 isolated mlink
[Service]
Type=simple
NetworkNamespacePath=/run/netns/{ns}
PrivateMounts=yes
TemporaryFileSystem=/run/netns
TemporaryFileSystem=/run/tt
ExecStart=/bin/bash {D}/mlink-private-start.sh
KillMode=mixed
TimeoutStopSec=80
LimitNOFILE=1048576
LimitMEMLOCK=infinity
''')
sp.run(['systemctl','daemon-reload'],check=True);sp.run(['systemctl','start','bench108-mlink'],check=True)
