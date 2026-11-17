#!/usr/bin/env python3
"""Launch the existing five-way workloads from a frozen, timestamped copy.

Default: show the plan, with no writes or benchmark activity.
Usage: sudo python3 start_formal_bench.py --start --exclusive-window
Run foreground inside tmux, or launch this command with systemd-run.
No model calls, binary changes, service restarts, or global cache clearing occur.
This includes five timing/resource rounds, three paired storage rounds,
0-to-50 instance growth, and 20 MiB arrays (zero, value 100, random).
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import write_sandbox_configs as cfg

# Section 1: Fixed scope and prerequisites.
SOURCE = cfg.DEPLOY / 'fiveway'
PYTHON = cfg.DEPLOY / 'venv/bin/python'
FILES = ('runner.py', 'retained.py', 'extent_accounting.py', 'summarize.py', 'storage-summary.py')

def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')

# Section 2: Freeze workload code and include renewed off endpoints in PSS.
def freeze(root):
    tools = root / 'tools'
    tools.mkdir()
    for name in FILES:
        shutil.copy2(SOURCE / name, tools / name)
    path = tools / 'runner.py'
    text = path.read_text()
    old = "if units[pr] in cg or (pr=='kuasar-off'"
    new = "if units[pr] in cg or (pr=='kuasar-off' and 'bench-kuasar-off-' in cg) or (pr=='kuasar-off'"
    if text.count(old) != 1:
        raise RuntimeError('Unexpected resource collector version; review before proceeding')
    text = text.replace(old, new)
    # The outer launcher holds one lock across timing, storage, and summaries.
    lock_line = "lk=open('/run/skyrl-threeway-benchmark.lock','w');fcntl.flock(lk,fcntl.LOCK_EX|fcntl.LOCK_NB)"
    for name in ('runner.py', 'retained.py'):
        p = tools / name
        content = text if name == 'runner.py' else p.read_text()
        if content.count(lock_line) != 1:
            raise RuntimeError('Unexpected lock implementation in ' + name)
        content = content.replace(lock_line, "assert os.environ.get('FIVEWAY_LOCK_HELD') == '1'")
        compile(content, str(p), 'exec')
        p.write_text(content)
    # Use mlink, not CubeSandbox, as the percentage comparison baseline.
    for name in ('summarize.py', 'storage-summary.py'):
        p = tools / name
        content = p.read_text().replace("x['product']=='cube'", "x['product']=='kuasar-mlink'")
        content = content.replace('cube_median=cb', 'mlink_median=cb').replace('cube=cb', 'mlink=cb')
        compile(content, str(p), 'exec')
        p.write_text(content)
    # Preserve hashes of the frozen workload sources.
    hashes = {name: hashlib.sha256((tools / name).read_bytes()).hexdigest() for name in FILES}
    save(root / 'workload-hashes.json', hashes)
    return tools

# Section 3: Freeze and execute the 50-instance memory workloads.
def memory50(root, tools):
    sources = {'growth': cfg.HOME / 'results/memory50-review/run.py',
               'arrays': cfg.HOME / 'results/array50-paired/run.py'}
    for group, source in sources.items():
        target = root / group
        target.mkdir()
        text = source.read_text()
        text, count = re.subn(r"sys.path.insert\(0,'[^']+'\)",
                             'sys.path.insert(0,' + repr(str(tools)) + ')', text)
        if count != 1:
            raise RuntimeError('Unexpected memory workload import: ' + str(source))
        if group == 'arrays':
            # Persist owned IDs immediately, including when a workload later fails.
            text = text.replace('owned.append(s);b.ready',
                 "owned.append(s);out['owned']=[b.sid(x) for x in owned];b.save(path,out);b.ready")
        compile(text, str(target / 'run.py'), 'exec')
        (target / 'run.py').write_text(text)
        save(target / 'source.json', {'original': str(source), 'sha256': hashlib.sha256(text.encode()).hexdigest()})
    for mode in ('growth', 'default', '100', 'random'):
        directory = root / ('growth' if mode == 'growth' else 'arrays')
        for product in cfg.PRODUCTS:
            command = ['nsenter', '--net=/run/netns/' + cfg.NAMESPACES[product], PYTHON,
                       directory / 'run.py', product]
            if mode != 'growth':
                command.append(mode)
            phase(root, 'memory-' + mode + '-' + product, command)
            record = directory / (product + ('' if mode == 'growth' else '-' + mode) + '.json')
            data = json.loads(record.read_text())
            if data.get('owned') or data.get('error') or data.get('cleanup_error') or data.get('cleanup_errors'):
                raise RuntimeError('Memory workload failed: ' + str(record))
            if mode == 'growth' and data.get('verified') != 50:
                raise RuntimeError('Incomplete instance growth test')
            if mode != 'growth' and not data.get('success'):
                raise RuntimeError('Incomplete array test')

# Section 4: Run a phase and retain errors rather than restarting automatically.
def phase(root, name, args):
    save(root / 'progress.json', {'phase': name, 'started_at': time.time()})
    environment = os.environ.copy()
    environment['FIVEWAY_LOCK_HELD'] = '1'
    with (root / (name + '.log')).open('w') as log:
        result = subprocess.run(list(map(str, args)), stdout=log, stderr=subprocess.STDOUT, env=environment)
    if result.returncode:
        save(root / 'blocked.json', {'phase': name, 'exit_code': result.returncode,
                                    'note': 'Inspect original logs and owned-instance ledgers before retrying.'})
        raise RuntimeError(name + ' failed; subsequent phases were not started')

# Section 5: Verify successful records and owned-instance cleanup.
def validate(directory, expected):
    rows = []
    for p in directory.glob('*.json'):
        data = json.loads(p.read_text())
        if isinstance(data, dict) and 'product' in data:
            rows.append(data)
    if len(rows) != expected:
        raise RuntimeError(f'{directory}: expected {expected} records, found {len(rows)}')
    for row in rows:
        if not row.get('success') or row.get('owned_remaining') or row.get('remaining'):
            raise RuntimeError('Failed workload or incomplete cleanup: ' + row['product'])
        if any(not request.get('success') for request in row.get('pressure', [])):
            raise RuntimeError('A throughput request failed: ' + row['product'])
    return len(rows)

# Section 6: Execute timing, resources, storage, and memory phases in order.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', action='store_true')
    parser.add_argument('--exclusive-window', action='store_true', help='Confirm other sessions will not submit work during measurement')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = args.output or cfg.HOME / 'results' / ('fiveway-formal-' + time.strftime('%Y%m%d_%H%M%S'))
    print('Products:', ', '.join(cfg.PRODUCTS))
    print('Timing/resource records: 25; paired storage records: 30')
    print('Memory: five growth tests and fifteen 20 MiB array tests')
    print('Output:', root)
    if not args.start:
        print('Plan only. Nothing was started.')
        return
    if os.geteuid() != 0 or not args.exclusive_window:
        raise SystemExit('Use sudo and --exclusive-window after coordinating other sessions.')
    held_lock = cfg.lock()
    for name in FILES:
        if not (SOURCE / name).is_file():
            raise FileNotFoundError(SOURCE / name)
    for product in cfg.PRODUCTS:
        cfg.require_idle(product)
    # Refuse to label results as 1000 ms / 16 if deployment settings drifted.
    import tomllib
    conf = tomllib.loads((cfg.HOME / 'data/mlink3/ttlet.toml').read_text())
    def values(tree, key):
        result = []
        for k, value in tree.items():
            if k == key:
                result.append(value)
            if isinstance(value, dict):
                result.extend(values(value, key))
        return result
    if values(conf, 'foreground_quiet_period_ms') != [1000] or values(conf, 'cleanup_concurrency') != [16]:
        raise SystemExit('mlink configuration differs from the agreed baseline.')
    root.mkdir(parents=True, exist_ok=False)
    try:
        tools = freeze(root)
        save(root / 'scope.json', {'products': cfg.PRODUCTS, 'reference': 'kuasar-mlink',
             'prefetch': 'off', 'quiet_period_ms': 1000, 'cleanup_concurrency': 16,
             'timing_rounds': 5, 'storage_rounds': 3, 'models_used': False,
             'storage_accounting': 'allocated bytes and extent accounting; inspect validity flags'})
        phase(root, 'timing', [PYTHON, tools / 'runner.py', 'run', root / 'timing'])
        validate(root / 'timing', 25)
        phase(root, 'storage', [PYTHON, tools / 'retained.py', 'run', root / 'timing/storage'])
        validate(root / 'timing/storage', 30)
        phase(root, 'timing-summary', [PYTHON, tools / 'summarize.py', root / 'timing'])
        phase(root, 'storage-summary', [PYTHON, tools / 'storage-summary.py', root / 'timing/storage'])
        memory50(root, tools)
        save(root / 'complete.json', {'timing_records': 25, 'storage_records': 30,
                                      'memory_cases': 20, 'finished_at': time.time()})
        print('Completed:', root)
    except BaseException as exc:
        save(root / 'blocked.json', {'error': str(exc), 'time': time.time()})
        raise

if __name__ == '__main__':
    main()
