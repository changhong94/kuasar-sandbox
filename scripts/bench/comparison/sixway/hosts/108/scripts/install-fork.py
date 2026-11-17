from pathlib import Path
import os,json,secrets,subprocess as sp,shutil,hashlib
M=Path('/opt/bench108');D=M/'deploy/fork';H=M/'data/fork';Q=M/'src/kuasar-fork/kuasar-io/kuasar';I=M/'import113/kuasar-oci'
assert os.geteuid()==0
D.mkdir(exist_ok=True);H.mkdir(exist_ok=True);(D/'empty-containerd').mkdir(exist_ok=True)
shutil.copytree(I/'bin',D/'bin',dirs_exist_ok=True)
key=D/'api-key'
if not key.exists():key.write_text(secrets.token_urlsafe(32));key.chmod(0o600)
repls={'/home/hong/deploy/kuasar-oci':str(D),'/home/hong/data/kuasar-oci':str(H),'/home/hong/src/research/sandbox_fork/kuasar-io/kuasar':str(Q),'/home/hong/src/research/sandbox_bench':str(M),'/home/hong/data/kuasar-fork/guest/vmlinuz':str(M/'assets/vmlinuz'),'/home/hong/data/kuasar-fork/guest/boot.cpio':str(M/'assets/boot.cpio'),'/home/hong/src/research/sandbox_fork/tools/oci-pool-10/runtime.ext4':str(M/'assets/fork-runtime.ext4'),'/run/kuasar-oci-113':'/run/bench108-fork','ociseed00001':'b108seed0001','oci-pool-seed':'b108-fork-seed',"B/'tools/cni'":"B/'assets/cni'","'python3',str(Path":"'"+str(M/'venv/bin/python')+"',str(Path","'--template','redis'":"'--template','base'"}
for name in ['config.toml','supervisor.py']:
 s=(I/name).read_text()
 for a,b in repls.items():s=s.replace(a,b)
 (D/name).write_text(s)
c=json.loads((I/'cni.json').read_text());c['name']='b108fork';c['bridge']='b108forkbr';(D/'cni.json').write_text(json.dumps(c))
# The comparison creates a command environment, like the original five-way harness.
# Generic slots attach the same immutable Python rootfs; no per-image VM pool.
(D/'images.json').write_text(json.dumps({'base':{'disk':str(M/'assets/python-base.ext4'),'manifest':'sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79','sha256':hashlib.sha256((M/'assets/python-base.ext4').read_bytes()).hexdigest()}}))
ns='b108-fork'
if not Path('/run/netns/'+ns).exists():sp.run(['ip','netns','add',ns],check=True)
sp.run(['ip','-n',ns,'link','set','lo','up'],check=True)
Path('/etc/systemd/system/bench108-fork.service').write_text(f'''[Unit]
Description=Six-way108 latest generic CoW fork pool
[Service]
NetworkNamespacePath=/run/netns/{ns}
ExecStart={M}/venv/bin/python {D}/supervisor.py
KillMode=control-group
TimeoutStopSec=30
LimitNOFILE=65536
Environment=E2B_DURABLE_STORE=sqlite
Environment=KUASAR_FORK_RUNTIME_DIR=/run/bench108-fork
Environment=E2B_TEMPLATE_POOL_SIZE=64
Environment=E2B_TEMPLATE_POOL_REFILL_DELAY_MS=1000
Environment=E2B_IMAGE_CATALOG={D}/images.json
''')
sp.run(['systemctl','daemon-reload'],check=True);sp.run(['systemctl','start','bench108-fork'],check=True)
