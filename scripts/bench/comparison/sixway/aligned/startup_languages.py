"""Run the aligned six-product startup protocol separately for each image."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from languages import PRODUCTS, select_language


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--languages', nargs='+', choices=['python', 'node', 'ruby'],
                        default=['python', 'node', 'ruby'])
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if len(set(args.languages)) != len(args.languages):
        parser.error('duplicate languages')
    # Validate every image before a partially configured matrix starts.
    for language in args.languages:
        select_language(config, language)
    args.out.mkdir(parents=True, exist_ok=False)
    for language in args.languages:
        selected = select_language(config, language)
        proofs = []
        gate_lock = open('/run/skyrl-threeway-benchmark.lock', 'a')
        fcntl.flock(gate_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for product in PRODUCTS:
            target = args.out / 'preflight' / f'{language}-{product}.json'
            subprocess.run(['nsenter', '--net=/run/netns/' + selected[product]['netns'],
                            sys.executable, str(Path(__file__).with_name('preflight_language.py')),
                            str(args.config.resolve()), '--language', language, '--product', product,
                            '--out', str(target)], check=True)
            proofs.append(json.loads(target.read_text()))
        if len({(p['version'], p['interpreter_sha256']) for p in proofs}) != 1:
            raise RuntimeError(f'{language}: interpreter identity differs between products')
        gate_lock.close()
        subprocess.run([sys.executable, str(Path(__file__).with_name('startup.py')),
                        str(args.config.resolve()), '--language', language,
                        '--out', str(args.out / language)], check=True)
        subprocess.run([sys.executable, str(Path(__file__).with_name('summarize_startup.py')),
                        '--config', str(args.config.resolve()), '--language', language,
                        '--input', str(args.out / language), '--out', str(args.out / language)], check=True)
    summary = {language: json.loads((args.out / language / 'summary.json').read_text())
               for language in args.languages}
    (args.out / 'languages-summary.json').write_text(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
