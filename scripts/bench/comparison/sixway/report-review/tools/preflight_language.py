"""Validate one prepared language template in a disposable sandbox, outside timing."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
from languages import LANGUAGES, PRODUCTS, select_language
from pool_gate import wait
from startup import setup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--language', required=True, choices=LANGUAGES)
    parser.add_argument('--product', required=True, choices=PRODUCTS)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    cfg = select_language(json.loads(args.config.read_text()), args.language)
    c, Sandbox = setup(args.product, cfg)
    wait(c)
    sandbox = None
    row = dict(language=args.language, product=args.product, success=False,
               image_digest=cfg['_image_digest'])
    def execute(command):
        if Sandbox:
            result = sandbox.commands.run(command, user='root', timeout=60)
            if result.exit_code: raise RuntimeError(result.stderr)
            return result.stdout
        return subprocess.check_output(c['ctl'] + ['exec', sandbox, '--insecure', '--user',
                'root', '--', '/bin/bash', '-l', '-c', command], text=True, timeout=90)
    try:
        if Sandbox:
            sandbox = Sandbox.create(c['template'], timeout=300, **c.get('create_kwargs', {}))
        else:
            sandbox = subprocess.check_output(c['ctl'] + ['start', c['template'], '--insecure',
                        '--timeout', '300'], text=True, timeout=90).strip()
        row['sandbox_id'] = sandbox.sandbox_id if Sandbox else sandbox
        processes = execute('for p in /proc/[0-9]*/comm; do cat "$p"; done').splitlines()
        assert not any(x.startswith(('python', 'node', 'ruby')) for x in processes), processes
        binary = LANGUAGES[args.language]['binary']
        text = execute('nproc; grep MemTotal /proc/meminfo; ' + shlex.quote(binary) +
                       ' --version; sha256sum ' + shlex.quote(binary)).strip().splitlines()
        assert text[0] == '2', text
        memory_kib = int(text[1].split()[1])
        assert 1900 * 1024 <= memory_kib <= 2048 * 1024, text
        row.update(success=True, vcpus=2, memory_kib=memory_kib, version=text[2],
                   interpreter_sha256=text[-1].split()[0], no_interpreter_running=True)
    finally:
        if sandbox is not None:
            if Sandbox: sandbox.kill()
            else: subprocess.run(c['ctl'] + ['delete', sandbox], check=True, timeout=90)
            row['destroyed'] = True
        wait(c)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(row, indent=2))
    print(json.dumps(row))


if __name__ == '__main__': main()
