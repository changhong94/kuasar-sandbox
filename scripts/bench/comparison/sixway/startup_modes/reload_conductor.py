"""Run via the owned service's ExecReload so replacement stays in its cgroup."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time

product = sys.argv[1]
unit, access_file, namespace = {
    'kuasar-off': ('kuasar-comparison-node.service', '/home/hong/deploy/comparison/kuasar-state/access.json', 'bench113'),
    'kuasar-uffd': ('bench-private-uffd-serve.service', '/home/hong/deploy/private-pilot/uffd-state/access.json', 'bench113-u'),
}[product]
access = json.loads(Path(access_file).read_text())
work = Path(access['work_dir'])
config = work/'conductor.yaml'
with sqlite3.connect((work/'lib/node-ctl.db').as_uri()+'?mode=ro', uri=True) as db:
    assert db.execute('SELECT COUNT(*) FROM sandboxes').fetchone()[0] == 0, 'Live sandboxes must not be interrupted'
candidates = []
for path in Path('/proc').glob('[0-9]*'):
    try:
        args = [s.decode() for s in (path/'cmdline').read_bytes().split(b'\0') if s]
        if 'conductor' in args and 'serve' in args and str(config) in args and unit in (path/'cgroup').read_text():
            candidates.append((path, args))
    except OSError:
        pass
assert len(candidates) == 1, 'Expected one owned conductor'
path, args = candidates[0]
env = dict(s.decode().split('=', 1) for s in (path/'environ').read_bytes().split(b'\0') if b'=' in s)
pid = int(path.name)
os.kill(pid, signal.SIGTERM)
for _ in range(300):
    if not path.exists() or (path/'stat').read_text().split(') ',1)[1].startswith('Z '):
        break
    time.sleep(.1)
else:
    raise TimeoutError('Owned conductor did not stop gracefully')
with (work/'orch.log').open('ab', buffering=0) as log:
    child = subprocess.Popen(['nsenter', '--net=/run/netns/'+namespace, *args], env=env,
        stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
time.sleep(.5)
assert child.poll() is None, 'Replacement conductor failed'
print(product, 'conductor reloaded in owned service', child.pid)
