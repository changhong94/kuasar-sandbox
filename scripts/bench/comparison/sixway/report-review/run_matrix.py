"""Run the supported mode matrix under the shared benchmark lock."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

B = Path('/home/hong/src/research/report-review-113')
T = B/'tools'
cfg = json.loads((T/'config.json').read_text())
PYTHON = '/home/hong/src/research/python-latest-113/venv/bin/python'
out = B/'results/matrix'
out.mkdir(exist_ok=True)
with open('/run/skyrl-threeway-benchmark.lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    env = {**os.environ, 'STARTUP_MODE_LOCK_HELD': '1'}
    for lang in ['python', 'node', 'ruby']:
        # Existing policy prepares a generic VM pool, never an interpreter.
        prep = time.monotonic_ns()
        subprocess.run([PYTHON, str(T/'switch-language.py'), str(T/'config.json'),
                        lang, str(out/'preparation'/lang)], check=True)
        print('PREPARED', lang, (time.monotonic_ns()-prep)/1e6, flush=True)
        for product in ['kuasar-fork', 'kuasar-mlink', 'agentenv', 'cube', 'kuasar-off', 'kuasar-uffd']:
            modes = (['local_warm', 'local_cold', 'remote'] if product == 'kuasar-fork' else
                     ['local_warm', 'local_cold', 'remote'] if product in ('kuasar-off', 'kuasar-uffd') else
                     ['product_default_warm'])
            for mode in modes:
                target = out/lang/product/mode
                if (target/'50.json').exists():
                    rows = [json.loads((target/f'{i:02d}.json').read_text()) for i in range(1,51)]
                    assert all(r['success'] and r['destroyed'] for r in rows)
                    print('COMPLETE_ALREADY', lang, product, mode, flush=True)
                    continue
                subprocess.run(['nsenter', '--net=/run/netns/'+cfg[product]['netns'],
                    PYTHON, str(B/'mode_worker.py'), product, lang, mode,
                    '--samples', '50', '--out', str(target)], check=True, env=env)
    (out/'complete.json').write_text(json.dumps({'samples_per_group': 50,
        'warmups_per_group': 1, 'cold_reset_before_every_request': True,
        'six_products': True, 'unsupported_modes_not_imputed': True}, indent=2))
