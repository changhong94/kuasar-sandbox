"""Export the exact pinned Manifest snapshot closure as native local artifacts.

The owned benchmark node must contain exactly one tenant key. Its encrypted
registry record is read without mutation; plaintext is used only in the
subprocess environment. Never print or persist keys.
"""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import sqlite3
import re

B = Path('/home/hong/codex-work/sevenway-fresh-181')
T = B/'tools'
sys.path.insert(0, str(T))
from baseline_startup import setup
def select_language(cfg,lang):
 c=json.loads(json.dumps(cfg))
 for pr in c['_languages'][lang]['templates']:c[pr]['template']=c['_languages'][lang]['templates'][pr]
 c['_language']=lang;c['_image_digest']=c['_languages'][lang]['digest'];return c

product = sys.argv[1]
access_path = {'kuasar-off': '/opt/bench108/deploy/off/access.json',
               'kuasar-uffd': '/opt/bench108/deploy/uffd/access.json'}[product]
access = json.loads(Path(access_path).read_text())
cfg = json.loads((T/'config.json').read_text())
ledger=B/(product+'-native.json');rows=json.load(open(ledger)) if ledger.exists() else []
with open('/run/skyrl-threeway-benchmark.lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for language in ['python', 'node', 'ruby']:
        if any(r['language']==language for r in rows):continue
        selected = select_language(cfg, language)
        c, Sandbox = setup(product, selected)
        database = Path(access['work_dir'])/'lib/node-ctl.db'
        with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as db:
            keys = db.execute('SELECT manifest_key_enc,manifest_key_hash FROM manifest_keys').fetchall()
        assert len(keys) == 1, 'Refuse ambiguous tenant registry'
        secret_config = (Path(access['work_dir'])/'conductor.yaml').read_text()
        match = re.search(r'^\s*encryption_key:\s*["\']?([0-9a-f:]+)', secret_config, re.M)
        assert match, 'No encryption key configuration'
        key = subprocess.check_output([str(B/'tools/unseal')],
            input=json.dumps({'Root': match[1], 'Sealed': keys[0][0]}), text=True)
        assert key and len(key) == 64
        if True:
            source = c['template'].split('-', 2)[2]
            source = base64.urlsafe_b64decode(source+'='*(-len(source)%4)).decode()
            name = 'startup-'+product+'-'+language
            digest = hashlib.sha256(name.encode()).hexdigest()
            target = B/'native'/digest[:2]/digest[2:4]/name
            target.mkdir(parents=True, exist_ok=True)
            started = time.monotonic_ns()
            args = [str(Path(access['bin'])/'sandbox-ctl'), 'publish',
                    '--manifest-config', str(Path(access['work_dir'])/'manifest.yaml'),
                    '--to-ref-location', name+'='+target.as_uri(), '--reduce-ref', 'any',
                    '--json', '--quiet', source]
            result = subprocess.run(args, env={**os.environ, 'MANIFEST_KEY': key},
                                    capture_output=True, text=True, timeout=600)
            (B/(product+'-'+language+'-publish.log')).write_text(result.stderr)
            assert result.returncode == 0, 'Publish failed; inspect private host log'
            data = json.loads(result.stdout)
            rows.append({'product': product, 'language': language,
                         'digest': selected['_image_digest'], 'source': source,
                         'location': name, 'directory': str(target),
                         'publish_ms': (time.monotonic_ns()-started)/1e6,
                         'result': data})
            (B/(product+'-native.json')).write_text(json.dumps(rows, indent=2))
            print(product, language, 'native publication complete', flush=True)
