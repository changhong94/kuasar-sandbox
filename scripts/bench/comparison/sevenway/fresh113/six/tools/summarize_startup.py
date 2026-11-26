"""Summarize one language; reject missing/failed/mixed-image measured samples."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import statistics
from languages import PRODUCTS, select_language


def stats(values):
    if not values:
        return None
    ordered = sorted(values)
    return dict(n=len(values), median=statistics.median(values),
                p95=ordered[math.ceil(.95 * len(values)) - 1],
                p99=ordered[math.ceil(.99 * len(values)) - 1], max=max(values))


def summarize(directory, config, language):
    config = select_language(config, language)
    result, flat, markers = {}, [], set()
    keys = ['api_ms', 'native_ready_ms', 'interpreter_print_ms', 'completion_ms',
            'api_to_exec_ms', 'exec_to_native_ms', 'native_to_interpreter_ms',
            'delete_ms', 'lifecycle_through_refill_ms', 'internal_ready_ms']
    for name in PRODUCTS:
        rows = [json.loads((directory / f'{i:02d}-{name}.json').read_text()) for i in range(1, 51)]
        for row in rows:
            assert row['product'] == name and row.get('language', 'python') == language
            assert row['success'] and row['destroyed'] and row['attempts'] == 1
            assert row['marker'] not in markers
            markers.add(row['marker'])
            assert row['image_digest'] == config['_image_digest']
            assert row['start_ns'] <= row['api_ns'] <= row['exec_request_ns'] <= row['native_received_ns'] <= row['received_ns']
            assert row['marker'] in row['received_marker']
            if language == 'python':  # Existing Python evidence remains readable.
                row.setdefault('interpreter_print_ms', row.get('python_print_ms'))
                row.setdefault('native_to_interpreter_ms', row.get('native_to_python_ms'))
            assert row['interpreter_print_ms'] == (row['received_ns'] - row['start_ns']) / 1e6
            if name in ('kuasar-fork', 'kuasar-mlink'):
                assert row['pool_before']['supported'] and row['pool_after']['supported']
        result[name] = {k: stats([r[k] for r in rows if r.get(k) is not None]) for k in keys}
        if language == 'python':
            result[name]['python_print_ms'] = result[name]['interpreter_print_ms']
            result[name]['native_to_python_ms'] = result[name]['native_to_interpreter_ms']
        if not rows[0]['pool_after']['supported']:
            result[name]['lifecycle_through_refill_ms'] = None
        for k in ('pool_before', 'pool_after'):
            result[name][k] = stats([r[k]['elapsed_ms'] for r in rows if r[k]['supported']])
        for i, row in enumerate(rows, 1):
            flat.append(dict(product=name, language=language, sample=i,
                             **{k: row.get(k) for k in keys}))
    return result, flat


def main():
    root = Path(os.environ.get('SIXWAY_ROOT', '/home/hong/src/research/sixway-aligned-20261117'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=root / 'tools/config.json')
    parser.add_argument('--input', type=Path, default=root / 'results/startup')
    parser.add_argument('--out', type=Path, default=root / 'results')
    parser.add_argument('--language', choices=['python', 'node', 'ruby'], default='python')
    args = parser.parse_args()
    result, flat = summarize(args.input, json.loads(args.config.read_text()), args.language)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'startup-stages.json').write_text(json.dumps(result, indent=2))
    with (args.out / 'startup-measurements.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(flat[0]))
        writer.writeheader(); writer.writerows(flat)
    print(json.dumps({n: v['interpreter_print_ms'] for n, v in result.items()}, indent=2))


if __name__ == '__main__': main()
