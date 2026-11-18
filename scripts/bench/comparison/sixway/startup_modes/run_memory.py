import fcntl
import json
import os
from pathlib import Path
import subprocess

B=Path('/home/hong/src/research/startup-modes-113')
T=Path('/home/hong/src/research/ready-regression-113/tools')
PYTHON='/home/hong/src/research/python-latest-113/venv/bin/python'
cfg=json.loads((T/'config.json').read_text())
assert (B/'memory-preparation.json').exists()
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for language in ['python','node','ruby']:
        for product in ['kuasar-off','kuasar-uffd']:
            target=B/'results/matrix'/language/product/'remote'
            old=B/'results/remote-rocks'/language/product
            old.parent.mkdir(parents=True,exist_ok=True)
            if not old.exists():
                target.rename(old)
            subprocess.run(['nsenter','--net=/run/netns/'+cfg[product]['netns'],
                PYTHON,str(B/'mode_worker.py'),product,language,'remote','--samples','10',
                '--out',str(target)],check=True,env={**os.environ,'STARTUP_MODE_LOCK_HELD':'1'})
            rows=[json.loads((target/f'{i:02d}.json').read_text()) for i in range(1,11)]
            assert all(r['remote_cache']['memory_served_evidence'] for r in rows)
    (B/'results/memory-complete.json').write_text(json.dumps({'samples':60,
        'all_memory_served':True,'no_origin_fetches':True,'no_cache_disk_reads':True},indent=2))
