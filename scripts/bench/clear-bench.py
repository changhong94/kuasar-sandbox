#!/usr/bin/env python3
"""Clear hong's owned Kuasar deployment and compiled outputs. Preserve source/results."""
import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--deployment-only', action='store_true', help='Remove deployment and its data only')
    scope.add_argument('--build-only', action='store_true', help='Clean builds only; refuses a live deployment')
    parser.add_argument('--dry-run', action='store_true', help='Show cleanup scope without removing anything')
    args = parser.parse_args()
    command = ([] if os.geteuid()==0 else ['sudo']) + ['python3', str(Path(__file__).resolve().with_name('bench_lifecycle.py')), 'clear']
    for name in ['deployment_only','build_only','dry_run']:
        if getattr(args,name): command.append('--'+name.replace('_','-'))
    return subprocess.run(command).returncode


if __name__=='__main__':
    raise SystemExit(main())
