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

B = Path('/home/hong/src/research/report-review-113')
T = B/'tools'
sys.path.insert(0, str(T))
from startup import setup, sample
from languages import select_language
from cache_state import condition


def cache_info(product):
    settings = json.loads((B/'remote-cache.json').read_text())[product]
    binary = str(B/'bin/cache-ctl')
    info = json.loads(subprocess.check_output([binary, 'info', '--endpoint',
        settings['endpoint'], '--json'], text=True))
    pid = subprocess.check_output(['systemctl','show',settings['service'],'-p','MainPID','--value'],text=True).strip()
    assert int(pid)>0
    io = dict((k,int(v)) for k,v in (line.split(':') for line in Path('/proc',pid,'io').read_text().splitlines()))
    return {'info':info,'process_io':{pid:io},'settings':settings,'backend':'rocksdb'}


def source_delta(before,after):
    def values(info):
        result={}
        for tier in info['tiered']['tiers']:
            for cf in tier.get('rocks',[]):
                for line in cf.get('database_statistics','').splitlines():
                    fields=line.split()
                    if len(fields)==4 and fields[1:3]==['COUNT',':']:
                        result[fields[0]]=int(fields[3])
        return result
    a,b=values(before['info']),values(after['info'])
    counters={}
    for source in ['memory','file','unknown']:
        counters[source]={}
        for unit in ['requests','bytes']:
            key='kuasar.chunk.'+source+'.'+unit
            assert key in a and key in b,'chunk source instrumentation missing'
            counters[source][unit]=b[key]-a[key]
    counters['origin']={unit:after['info']['tiered']['origin'][field]-before['info']['tiered']['origin'][field]
                       for unit,field in [('requests','chunk_hits'),('bytes','chunk_bytes')]}
    for unit in ['requests','bytes']:
        total=sum(v[unit] for v in counters.values())
        for v in counters.values():v[unit+'_percent']=100*v[unit]/total if total else None
    return {'categories':counters,'bytes_definition':'encoded encrypted chunk payload returned by the cache',
            'requests_definition':'successful chunk reads; repeated reads count repeatedly; zero and hole ranges require no chunk request',
            'file_definition':'RocksDB payload file read; not necessarily physical device IO',
            'scope':'before create through completion of first print command, before destruction',
            'unknown_definition':'inline payload with file IO that cannot be separated from index/filter IO'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('product')
    parser.add_argument('language')
    parser.add_argument('mode', choices=['local_warm', 'local_cold', 'remote', 'product_default_warm'])
    parser.add_argument('--samples', type=int, default=50)
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
            directory = Path(entry['directory'])
            names = [entry['result'][k].split('@',1)[0][7:] for k in ('snapshotRef','sandboxRef')]
            paths = sorted({*(directory/name for name in names), *directory.glob('*.image')})
            assert all(p.is_file() and not p.is_symlink() for p in paths)
        assert paths
    c, Sandbox = setup(args.product, config)
    if args.mode == 'remote' and args.product == 'kuasar-fork':
        c['create_kwargs']={**c.get('create_kwargs',{}), 'metadata':{'kuasar.snapshot.mode':'manifest'}}
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
            observed = []
            if remote_before:
                c['startup_complete_observer'] = lambda: observed.append(cache_info(args.product))
            ok = sample(args.product, config, out, c, Sandbox)
            row = json.loads(out.read_text())
            # Old startup.py's ready_ms alias meant interpreter print. Correct
            # the public field names explicitly and retain separate endpoints.
            row.update(mode=args.mode, ready_ms=row.get('native_ready_ms'),
                       print_ms=row.get('interpreter_print_ms'), warmup=index == 0,
                       cache_preparation=proof)
            if remote_before:
                assert observed, 'startup completion observation missing'
                after = observed[0]
                assert set(after['process_io']) == set(remote_before['process_io'])
                read_bytes = sum(after['process_io'][pid]['read_bytes']-io['read_bytes']
                                 for pid,io in remote_before['process_io'].items())
                row['remote_cache'] = {'before':remote_before,'after':after,
                    'cache_daemon_disk_read_bytes':read_bytes,'source_percentages':source_delta(remote_before,after),
                    'backend':'rocksdb','direct_reads':True}
            out.write_text(json.dumps(row, indent=2))
            print(args.product, args.language, args.mode, index, ok,
                  row.get('ready_ms'), row.get('print_ms'), flush=True)
            assert ok, row.get('error', row.get('pool_refill_error'))
        if args.product == 'kuasar-fork':
            (args.out/'host.log').write_bytes(subprocess.check_output(['journalctl',
                '-u', 'bench-python113-fork', '--since', '@'+str(started_wall), '--no-pager', '-o', 'cat']))


if __name__ == '__main__':
    main()
