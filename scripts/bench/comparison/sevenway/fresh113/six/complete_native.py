"""Materialize immutable image references as well as S/E native carriers.

Run only while the owning matrix coordinator is paused and no sample is active.
The coordinator retains the exclusive benchmark lock for this preparation.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time

import fcntl
_bench_lock=open('/run/skyrl-threeway-benchmark.lock','a')
fcntl.flock(_bench_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
B = Path('/home/hong/src/research/sevenway-current-20261126/six')
for product, access_file in [
    ('kuasar-off', '/home/hong/deploy/comparison/kuasar-state/access.json'),
    ('kuasar-uffd', '/home/hong/deploy/private-pilot/uffd-state/access.json')]:
    access = json.loads(Path(access_file).read_text())
    work = Path(access['work_dir'])
    with sqlite3.connect((work/'lib/node-ctl.db').as_uri()+'?mode=ro', uri=True) as db:
        assert db.execute('SELECT COUNT(*) FROM sandboxes').fetchone()[0] == 0
        keys = db.execute('SELECT manifest_key_enc FROM manifest_keys').fetchall()
    assert len(keys) == 1
    match = re.search(r'^\s*encryption_key:\s*["\']?([0-9a-f:]+)', (work/'conductor.yaml').read_text(), re.M)
    key = subprocess.check_output([str(B/'unseal')], input=json.dumps({'Root': match[1], 'Sealed': keys[0][0]}), text=True)
    env = {**os.environ, 'MANIFEST_KEY': key}
    binary = Path(access['bin'])
    manifest = ['--manifest-config', str(work/'manifest.yaml')]
    entries = json.loads((B/(product+'-native.json')).read_text())
    for entry in entries:
        start = time.monotonic_ns()
        directory = Path(entry['directory'])
        location = entry['location']+'='+directory.as_uri()
        root = entry['result']['snapshotRef']
        def info(ref):
            return json.loads(subprocess.check_output([str(binary/'sandbox-ctl'), 'info',
                '--json', *manifest, '--ref-location', location, ref], env=env, text=True))
        metadata = info(root)
        def refs(value):
            if isinstance(value, dict):
                return set().union(*(refs(v) for v in value.values())) if value else set()
            if isinstance(value, list):
                return set().union(*(refs(v) for v in value)) if value else set()
            return {value} if isinstance(value,str) and value.startswith('manifest://') else set()
        replacements = []
        image_refs = sorted(refs(metadata))
        for index, ref in enumerate(image_refs):
            target = directory/f'import-{index}.image'
            subprocess.run([str(binary/'manifest-ctl'), 'load', *manifest,
                '--no-progress', '--output', str(target), '--name', 'image', ref],
                env=env, check=True, stdout=subprocess.DEVNULL)
            with target.open('rb') as f:
                f.seek(max(0, target.stat().st_size-65536))
                identities = re.findall(rb'\.kuasar\.digest\.([a-f0-9]{64})', f.read())
            assert identities, 'Native identity trailer missing'
            identity = identities[-1].decode()
            final = directory/(identity+'.image')
            target.replace(final)
            new_ref = 'file://'+final.name+'@digest:'+identity+'@location:'+entry['location']
            replacements += ['--replace-ref', ref+'='+new_ref]
        if replacements:
            result = subprocess.check_output([str(binary/'sandbox-ctl'), 'publish',
                '--json', '--quiet', *manifest, '--ref-location', location,
                '--to-ref-location', location, *replacements, root], env=env, text=True)
            entry['initial_result'] = entry['result']
            entry['result'] = json.loads(result)
        assert not refs(info(entry['result']['snapshotRef'])), 'Manifest dependency remains in local root'
        entry['immutable_images_materialized'] = len(image_refs)
        entry['image_materialization_ms'] = (time.monotonic_ns()-start)/1e6
        entry['resolved_config_has_manifest_refs'] = False
        print(product, entry['language'], 'full native closure', len(image_refs), flush=True)
    (B/(product+'-native.json')).write_text(json.dumps(entries, indent=2))
