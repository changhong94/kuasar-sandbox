from pathlib import Path
import subprocess as sp
import fcntl
import shutil
import os
import time
import json

b = Path('/home/hong/src/research/startup-modes-113')
p = Path('/home/hong/src/research/python-latest-113/deploy/fork')
with open('/run/skyrl-threeway-benchmark.lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    started = time.monotonic_ns()
    backup = b/'backups'
    backup.mkdir(exist_ok=True)
    assert not (backup/'cloud-hypervisor').exists()
    shutil.copyfile(p/'bin/cloud-hypervisor', backup/'cloud-hypervisor')
    sp.run(['ip', 'netns', 'exec', 'py113-fork', 'env', 'POOL_RESET_STOPPED=1',
            'python3', '/home/hong/src/research/sixway-aligned-20261117/tools/reset-fork.py'], check=True)
    source = Path('/home/hong/src/research/sixway-integrated-20261118/ch-target/release/cloud-hypervisor')
    temporary = p/'bin/cloud-hypervisor.next'
    shutil.copyfile(source, temporary)
    temporary.chmod(0o755)
    with temporary.open('rb') as f:
        os.fsync(f.fileno())
    temporary.replace(p/'bin/cloud-hypervisor')
    fd = os.open(p/'bin', os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    drop = Path('/etc/systemd/system/bench-python113-fork.service.d/startup-modes-trace.conf')
    drop.write_text('[Service]\nEnvironment=CH_FORK_TIMING=1\n')
    sp.run(['systemctl', 'daemon-reload'], check=True)
    sp.run(['systemctl', 'start', 'bench-python113-fork'], check=True)
    code = "import sys,json;sys.path.insert(0,'/home/hong/src/research/ready-regression-113/tools');from pool_gate import wait;c=json.load(open('/home/hong/src/research/ready-regression-113/tools/config.json'));print(json.dumps(wait(c['kuasar-fork'],timeout=300)))"
    out = sp.check_output(['ip', 'netns', 'exec', 'py113-fork', 'python3', '-c', code], text=True)
    (b/'trace-deployment.json').write_text(json.dumps({
        'elapsed_ms': (time.monotonic_ns()-started)/1e6, 'pool': json.loads(out)}, indent=2))
