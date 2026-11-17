from pathlib import Path
import subprocess as sp,os,shutil
M=Path('/opt/bench108');I=M/'import113/comparison';unit=Path('/etc/systemd/system')
assert os.geteuid()==0
for kind in ['off','uffd']:
 D=M/'deploy'/kind;D.mkdir(exist_ok=True);H=M/'data'/kind;H.mkdir(exist_ok=True);runid=kind+'108a1';ns='b108-'+kind
 if not Path('/run/netns',ns).exists():sp.run(['ip','netns','add',ns],check=True)
 sp.run(['ip','-n',ns,'link','set','lo','up'],check=True)
 if sp.run(['ip','-n',ns,'link','show','b0'],stdout=sp.DEVNULL,stderr=sp.DEVNULL).returncode:
  for args in [['link','add','b0','type','dummy'],['addr','add','192.0.2.108/24','dev','b0'],['link','set','b0','up'],['route','add','default','via','192.0.2.1']]:sp.run(['ip','-n',ns,*args],check=True)
 if kind=='off':B=I/'releases/kuasar-release-v0.1.6/bin';inputs=[I/'kuasar-state/demo_prep.sh',I/'kuasar-state/demo_e2b.sh']
 else:B=M/'src/kuasar-uffd/private/kuasar-uffd/kuasar-sandbox/bin/x86_64';inputs=[M/'import113/private-pilot/uffd-prep.sh',M/'import113/private-pilot/uffd-serve.sh']
 # Product source/binaries remain preserved; adapted runnable copies use local glibc loader only where needed.
 shutil.copytree(B,D/'bin',dirs_exist_ok=True);B=D/'bin'
 for f in B.iterdir():
  if f.is_file() and b'GLIBC_2.38' in f.read_bytes():sp.run(['patchelf','--set-interpreter',str(M/'assets/compat-lib/ld-linux-x86-64.so.2'),'--set-rpath',str(M/'assets/compat-lib'),str(f)],check=True)
 for name,source in zip(['prep','serve'],inputs):
  s=source.read_text().replace('/home/hong/deploy/comparison',str(I)).replace('/home/hong/src/private/kuasar-uffd',str(M/'src/kuasar-uffd/private/kuasar-uffd')).replace('/home/hong/deploy/private-pilot/uffd-state/access.json',str(D/'access.json')).replace(str(I/'kuasar-state/access.json'),str(D/'access.json'))
  if name=='prep':
   if kind=='off':
    a=s.index('DEMO_IMAGE_PLATFORM="$(demo_native_platform)"');b=s.index('ENV_TMP=',a)
    s=s[:a]+f'''SOURCE_IMAGE_ID=sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79
skopeo copy --preserve-digests --dest-tls-verify=false oci-archive:{I}/assets/scoring-base.oci.tar "docker://$REGISTRY/$REGISTRY_NS/base:local"
BASE_REF="$REGISTRY/$REGISTRY_NS/base@$SOURCE_IMAGE_ID"
skopeo inspect --raw --tls-verify=false "docker://$BASE_REF" | sha256sum | grep -q "${{SOURCE_IMAGE_ID#sha256:}}"
'''+s[b:]
  (D/(name+'.sh')).write_text(s)
 hosts=D/'hosts';hosts.write_text('127.0.0.1 localhost\n::1 localhost\n')
 common=f'''NetworkNamespacePath=/run/netns/{ns}
BindPaths={hosts}:/etc/hosts
Environment=DEMO_DATA_DIR={H}
Environment=BIN={B}
Environment=DEMO_QUICKSTART=1
Environment=ZOT_BIN={I}/zot
Environment=PYTHON_BIN={M}/venv/bin/python
Environment=DEMO_KEEP=1
Environment=DEMO_RUN_ID={runid}
Environment=DOMAIN=sandboxes.{kind}108.local
Environment=PATH={B}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=NO_PROXY=*
'''
 for name in ['prep','serve']:
  dependency=f'Requires=bench108-{kind}-prep.service\nAfter=bench108-{kind}-prep.service\n' if name=='serve' else ''
  typ='Type=oneshot\nRemainAfterExit=yes\n' if name=='prep' else 'Type=simple\n'
  (unit/f'bench108-{kind}-{name}.service').write_text('[Unit]\nDescription=Sixway108 '+kind+' '+name+'\n'+dependency+'[Service]\n'+typ+common+f'ExecStart=/bin/bash {D}/{name}.sh\nTimeoutStartSec=600\nTimeoutStopSec=60\nKillMode=mixed\nLimitNOFILE=1048576\n')
 drop=unit/f'kuasar-demo-{runid}-.service.d';drop.mkdir(exist_ok=True);(drop/'network.conf').write_text('[Service]\nNetworkNamespacePath=/run/netns/'+ns+'\n')
sp.run(['systemctl','daemon-reload'],check=True)
for kind in ['off','uffd']:sp.run(['systemctl','start','--no-block','bench108-'+kind+'-serve'],check=True)
