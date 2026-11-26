"""HTTP live-parent fork. Never replaces the source with a pool slot.

Run as root inside the owned fork network namespace. Holds the common benchmark
lock. Each sample owns a fresh source and child; artifacts survive cleanup.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import urllib.request
import uuid

BASE = Path('/home/hong/codex-work/sevenway-fresh-181')
DEPLOY = Path('/opt/bench108/deploy/fork')
TOOLS = BASE/'tools'
# Complete the failed pool group before live-fork measurements; successful rows skip.
subprocess.run([sys.executable,str(TOOLS/'legacy_pool181.py'),'kuasar-fork'],check=True)
sys.path.insert(0, str(TOOLS))
from languages import select_language, print_command
from pool_gate import wait as pool_wait
from baseline_startup import setup


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def request(c, path, data=None):
    req = urllib.request.Request(c['api_url'] + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={'X-API-Key': Path(c['key_file']).read_text().strip(),
                 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail=error.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {error.code} {path}: {detail}") from error


def command(s, text):
    r = s.commands.run(text, user='root', cwd='/', timeout=90)
    assert r.exit_code == 0, (r.exit_code, r.stderr)
    return r.stdout.strip()


def network_ready(c, sid):
    start = time.monotonic_ns()
    while time.monotonic_ns() - start < 60_000_000_000:
        info = request(c, '/sandboxes/' + sid)
        if info.get('metadata', {}).get('kuasar.network.status') == 'ready':
            return (time.monotonic_ns()-start)/1e6
        time.sleep(.02)
    raise TimeoutError('parent network readiness')


def progress(s):
    text = command(s, 'cat /tmp/live-progress.log')
    rows = [list(map(int, line.split())) for line in text.splitlines()]
    assert len(rows) > 1 and all(len(x) == 3 for x in rows), text
    assert all(b[1] == a[1]+1 for a, b in zip(rows, rows[1:])), rows
    return rows


def sample(config, language, index, output, Sandbox):
    c = config['kuasar-fork']
    owned = {}
    unconnected_child = None
    row = {'mode': 'live_parent_fork', 'language': language, 'index': index,
           'image_digest': config['_image_digest'], 'success': False,
           'clock': time.get_clock_info('monotonic').implementation,
           'guest_probe_period_ms': 10, 'start_unix_ns': time.time_ns()}
    start_wall = int(time.time())
    unit_log = Path("/nonexistent-use-journal181")
    log_offset = unit_log.stat().st_size if unit_log.exists() else None
    def remember(s):
        owned[s.sandbox_id] = s
        write(output/'owned.json', list(owned))
        return s
    def destroy(s):
        s.kill()
        del owned[s.sandbox_id]
        write(output/'owned.json', list(owned))
    try:
        row['pool_before'] = pool_wait(c, timeout=600)
        prep = time.monotonic_ns()
        parent = remember(Sandbox.create(c['template'], timeout=600, request_timeout=180))
        row['parent_id'] = parent.sandbox_id
        parent.files.write('/tmp/live-progress', (BASE/'progress').read_bytes(), user='root')
        command(parent, 'chmod 700 /tmp/live-progress; nohup /tmp/live-progress >/tmp/live-progress.log 2>/tmp/live-progress.err </dev/null &')
        marker = uuid.uuid4().hex
        parent.files.write('/tmp/live-proof', marker.encode(), user='root')
        command(parent, 'sync /tmp/live-proof')
        row['parent_network_wait_ms'] = network_ready(c, parent.sandbox_id)
        time.sleep(.05)
        before = progress(parent)
        row['preparation_ms'] = (time.monotonic_ns()-prep)/1e6
        native = 'NATIVE_'+uuid.uuid4().hex
        printed = 'READY_'+uuid.uuid4().hex
        cmd, code = print_command(language, printed, native)
        row.update(command=cmd, interpreter_code=code, parent_before=before[-1])
        row['start_ns'] = time.monotonic_ns()
        response = request(c, '/sandboxes/'+parent.sandbox_id+'/fork', {'count': 1, 'timeout': 600})
        row['api_ns'] = time.monotonic_ns()
        sid = response[0]['sandbox']['sandboxID']
        unconnected_child = sid
        row['child_id'] = sid
        # Ledger before connect so a connect failure cannot lose the new child.
        write(output/'pending-child.json', {'sandbox_id': sid})
        child = remember(Sandbox.connect(sid, timeout=600, request_timeout=180))
        unconnected_child = None
        row['connect_ns'] = time.monotonic_ns()
        chunks = []
        def receive(chunk):
            chunks.append(chunk)
            text = ''.join(chunks)
            if 'ready_ns' not in row and native+'\n' in text:
                row['ready_ns'] = time.monotonic_ns()
            if 'print_ns' not in row and printed+'\n' in text:
                row['print_ns'] = time.monotonic_ns()
        row['exec_ns'] = time.monotonic_ns()
        result = child.commands.run(cmd, user='root', cwd='/', timeout=90, on_stdout=receive)
        row['exec_done_ns'] = time.monotonic_ns()
        assert result.exit_code == 0 and 'print_ns' in row, (result.exit_code, result.stderr)
        for key in ['api', 'connect', 'ready', 'print']:
            row[key+'_ms'] = (row[key+'_ns']-row['start_ns'])/1e6
        # State correctness is checked after the startup stopwatch ends.
        a, b = progress(parent), progress(child)
        assert a[-1][1] > before[-1][1] and b[-1][1] > before[-1][1]
        assert a[-1][0] == b[-1][0] == before[-1][0]
        assert child.files.read('/tmp/live-proof', format='bytes', user='root') == marker.encode()
        parent.files.write('/tmp/live-proof', b'parent', user='root')
        child.files.write('/tmp/live-proof', b'child', user='root')
        assert parent.files.read('/tmp/live-proof', format='bytes', user='root') == b'parent'
        assert child.files.read('/tmp/live-proof', format='bytes', user='root') == b'child'
        row['parent_progress_gap_ms'] = max((y[2]-x[2])/1e6 for x,y in zip(a,a[1:]))
        row['parent_progress'] = a
        row['child_progress'] = b
        first, survivor = (parent, child) if index % 2 == 0 else (child, parent)
        expected = b'child' if survivor is child else b'parent'
        old_counter = progress(survivor)[-1][1]
        row['destroy_first'] = 'parent' if first is parent else 'child'
        destroy(first)
        assert survivor.files.read('/tmp/live-proof', format='bytes', user='root') == expected
        assert progress(survivor)[-1][1] > old_counter
        assert command(survivor, cmd).endswith(printed)
        destroy(survivor)
        row.update(success=True, inherited_process_continues=True,
                   independent_files=True, independent_destroy=True)
    except Exception as error:
        row['error'] = repr(error)
        raise
    finally:
        for sid, s in list(owned.items()):
            try: destroy(s)
            except Exception as error: row.setdefault('cleanup_errors', []).append(repr(error))
        if unconnected_child:
            req = urllib.request.Request(c['api_url']+'/sandboxes/'+unconnected_child,
                method='DELETE', headers={'X-API-Key': Path(c['key_file']).read_text().strip()})
            try:
                with urllib.request.urlopen(req, timeout=180):
                    pass
            except Exception as error:
                row.setdefault('cleanup_errors', []).append(repr(error))
        row['owned_remaining'] = list(owned)
        row['end_unix_ns'] = time.time_ns()
        write(output/'result.json', row)
        if log_offset is not None:
            with unit_log.open('rb') as log:
                assert unit_log.stat().st_size >= log_offset, 'unit log rotated during sample'
                log.seek(log_offset)
                (output/'host.log').write_bytes(log.read())
        else:
            (output/'host.log').write_bytes(subprocess.check_output([
                'journalctl', '-u', 'bench108-fork', '--since', '@'+str(start_wall),
                '--no-pager', '-o', 'cat']))
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=50)
    parser.add_argument('--languages', nargs='+', default=['python', 'node', 'ruby'])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with open('/run/skyrl-threeway-benchmark.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = json.loads((TOOLS/'config.json').read_text())
        config.pop('fork2',None)
        for entry in config['_languages'].values(): entry['templates'].pop('fork2',None)
        rows = []
        for language in args.languages:
            selected = select_language(config, language)
            c, Sandbox = setup('kuasar-fork', selected)
            for index in range(args.samples+1):
                out = args.out/language/('warmup' if index == 0 else f'{index:02d}')
                out.mkdir(parents=True, exist_ok=True)
                previous = out/'result.json'
                if previous.exists():
                    old=json.loads(previous.read_text())
                    if old.get('success') and not old.get('owned_remaining'):
                        if index: rows.append(old)
                        continue
                    raise RuntimeError('Review previous failure: '+str(previous))
                row = sample(selected, language, index, out, Sandbox)
                if index: rows.append(row)
                write(args.out/'rows.json', rows)
                print(language, index, row['ready_ms'], row['print_ms'], flush=True)


if __name__ == '__main__':
    main()
