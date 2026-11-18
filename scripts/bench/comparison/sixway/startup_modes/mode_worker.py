"""Serial timed samples with independently verified cache state per request."""
import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

B = Path('/home/hong/src/research/startup-modes-113')
T = Path('/home/hong/src/research/ready-regression-113/tools')
sys.path.insert(0, str(T))
from startup import setup, sample
from languages import select_language
from cache_state import condition


def cache_info(product):
    root = '/home/hong/data/uffd' if product == 'kuasar-uffd' else '/home/hong/data/comparison/cube-xfs/kuasar'
    binary = '/home/hong/src/private/kuasar-uffd/kuasar-sandbox/bin/x86_64/cache-ctl'
    settings = json.loads((B/'remote-cache.json').read_text())[product] if (B/'remote-cache.json').exists() else None
    endpoint = settings['endpoint'] if settings else 'unix://'+root+'/run/cache-health.sock'
    info = json.loads(subprocess.check_output([binary, 'info', '--endpoint',
        endpoint, '--json'], text=True))
    processes = {}
    redis_pid = None
    if settings:
        redis_pid = subprocess.check_output(['docker','-H','unix:///run/cube-comparison/docker.sock',
            'inspect','--format','{{.State.Pid}}','bench-startup-modes-redis'],text=True).strip()
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            cmd = (proc/'cmdline').read_bytes()
            is_cache = b'cache-ctl' in cmd and (settings['config'] if settings else root).encode() in cmd
            if not is_cache and proc.name != redis_pid:
                continue
            processes[proc.name] = dict((k, int(v)) for k,v in
                (line.split(':') for line in (proc/'io').read_text().splitlines()))
        except OSError:
            continue
    assert processes, 'Cache daemon I/O accounting missing'
    return {'info': info, 'process_io': processes, 'settings': settings,
            'backend': 'redis-memory' if settings else 'rocks-blobdb'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('product')
    parser.add_argument('language')
    parser.add_argument('mode', choices=['local_warm', 'local_cold', 'remote', 'product_default_warm'])
    parser.add_argument('--samples', type=int, default=10)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    config = select_language(json.loads((T/'config.json').read_text()), args.language)
    paths = []
    if args.mode.startswith('local_'):
        if args.product == 'kuasar-fork':
            prep = json.loads(Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json.snapshot-preparation.json').read_text())
            entry = prep[config[args.product]['template']]
            directory = Path(entry['directory'])
            paths = sorted(p for p in directory.iterdir() if p.is_file())
        else:
            entries = json.loads((B/(args.product+'-native.json')).read_text())
            entry = next(e for e in entries if e['language'] == args.language)
            ref = entry['result']['snapshotRef']
            config[args.product]['template'] = 'e2b-snp-'+base64.urlsafe_b64encode(ref.encode()).decode().rstrip('=')
            paths = sorted(p for p in Path(entry['directory']).iterdir() if p.is_file())
        assert paths
    c, Sandbox = setup(args.product, config)
    with open('/run/skyrl-threeway-benchmark.lock', 'a') as lock:
        if os.environ.get('STARTUP_MODE_LOCK_HELD') != '1':
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started_wall = int(time.time())
        for index in range(args.samples+1):
            name = 'warmup' if index == 0 else f'{index:02d}'
            out = args.out/(name+'.json')
            proof = condition(paths, args.mode) if paths else None
            if proof:
                (args.out/(name+'-cache.json')).write_text(json.dumps(proof, indent=2))
            remote_before = cache_info(args.product) if args.mode == 'remote' else None
            ok = sample(args.product, config, out, c, Sandbox)
            row = json.loads(out.read_text())
            # Old startup.py's ready_ms alias meant interpreter print. Correct
            # the public field names explicitly and retain separate endpoints.
            row.update(mode=args.mode, ready_ms=row.get('native_ready_ms'),
                       print_ms=row.get('interpreter_print_ms'), warmup=index == 0,
                       cache_preparation=proof)
            if remote_before:
                after = cache_info(args.product)
                assert set(after['process_io']) == set(remote_before['process_io'])
                read_bytes = sum(after['process_io'][pid]['read_bytes']-io['read_bytes']
                                 for pid,io in remote_before['process_io'].items())
                origin = after['info']['tiered']['origin']['hits']-remote_before['info']['tiered']['origin']['hits']
                hits = after['info']['server']['hits']-remote_before['info']['server']['hits']
                row['remote_cache'] = {'before': remote_before, 'after': after,
                    'cache_daemon_disk_read_bytes': read_bytes, 'origin_fetches': origin,
                    'cache_hits': hits,
                    'memory_served_evidence': read_bytes == 0 and origin == 0 and hits > 0,
                    'backend': after['backend'],
                    'direct_reads': None if after['settings'] else True}
            out.write_text(json.dumps(row, indent=2))
            print(args.product, args.language, args.mode, index, ok,
                  row.get('ready_ms'), row.get('print_ms'), flush=True)
            assert ok, row.get('error', row.get('pool_refill_error'))
        if args.product == 'kuasar-fork':
            (args.out/'host.log').write_bytes(subprocess.check_output(['journalctl',
                '-u', 'bench-python113-fork', '--since', '@'+str(started_wall), '--no-pager', '-o', 'cat']))


if __name__ == '__main__':
    main()
