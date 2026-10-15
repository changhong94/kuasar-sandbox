#!/usr/bin/env python3
"""Prepare dependencies, build official Kuasar, and deploy the owned bench node.

Run as the deployment user (sudo is used only for apt), or via sudo.
--check performs a read-only inspection. Go/Rust and Docker are prerequisites;
toolchains are never replaced. --deps-only skips build/deployment.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import subprocess
import sys

PACKAGES = '''build-essential autoconf automake bc bison flex clang cmake cpio
 gawk gperf libaio-dev libbpf-dev libbz2-dev libcap-dev libclang-dev libelf-dev
 libfuse3-dev libgcrypt20-dev libgflags-dev liblz4-dev libncurses-dev libnuma-dev
 libseccomp-dev libsnappy-dev libssl-dev libtool libtool-bin liburing-dev
 libzstd-dev lld llvm lz4 ninja-build pkg-config python3-venv python3-pip
 python3-yaml rsync skopeo socat sqlite3 uuid-dev zlib1g-dev zstd erofs-utils jq
 git curl ca-certificates openssl tar gzip xz-utils unzip file iproute2 iptables
 util-linux procps'''.split()


def run(cmd, capture=False):
    print('+', shlex.join(map(str, cmd)), flush=True)
    return subprocess.run(list(map(str, cmd)), check=True, text=True,
                          stdout=subprocess.PIPE if capture else None)


def installed_packages():
    result = subprocess.check_output(
        ['dpkg-query', '-W', '-f=${binary:Package}\t${Status}\n'], text=True)
    return {line.split('\t')[0].split(':')[0] for line in result.splitlines()
            if line.endswith('\tinstall ok installed')}


def locked_requirements(path):
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s;]+)', line)
        if not match:
            raise RuntimeError('Unsupported requirements entry: ' + line)
        result[re.sub(r'[-_.]+', '-', match[1]).lower()] = match[2]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Inspect only; change nothing')
    parser.add_argument('--venv', type=Path, help='Dedicated bench virtual environment')
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--deps-only', action='store_true', help='Only prepare dependencies')
    scope.add_argument('--build-only', action='store_true', help='Prepare dependencies and compile, without deploying')
    parser.add_argument('--timeout', type=int, default=600, help='Deployment readiness timeout in seconds')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    if args.venv and not (args.deps_only or args.check):
        parser.error('--venv is supported with --deps-only/--check; deployment uses its configured bench-venv')
    if sys.platform != 'linux' or not shutil.which('apt-get'):
        parser.error('Requires Ubuntu/Debian Linux with apt-get')
    user = pwd.getpwnam(os.environ.get('SUDO_USER') or pwd.getpwuid(os.getuid()).pw_name)
    home = Path(user.pw_dir)
    venv = (args.venv or home/'src/.deployment/bench-venv').absolute()
    python = venv/'bin/python'
    lock = Path(__file__).resolve().with_name('requirements.lock.txt')
    wanted = locked_requirements(lock)
    # Keep user-owned environment even when this script is called through sudo.
    user_prefix = ['runuser', '-u', user.pw_name, '--'] if os.geteuid() == 0 and user.pw_uid else []
    sudo = [] if os.geteuid() == 0 else ['sudo']
    missing = sorted(set(PACKAGES) - installed_packages())
    print('Missing system packages:', ', '.join(missing) or 'none')
    if venv.exists() and not (venv/'pyvenv.cfg').is_file():
        raise RuntimeError(f'Refusing to overwrite non-venv directory: {venv}')
    have = {}
    if (venv/'pyvenv.cfg').is_file():
        if not python.exists():
            raise RuntimeError(f'Existing venv is broken; leaving it unchanged: {venv}')
        probe = 'import importlib.metadata,json; print(json.dumps({d.metadata["Name"]:d.version for d in importlib.metadata.distributions()}))'
        output = subprocess.check_output(user_prefix+[str(python), '-c', probe], text=True)
        have = {re.sub(r'[-_.]+', '-', k).lower(): v for k, v in json.loads(output).items()}
    conflicts = [f'{k}: installed {have[k]}, required {v}' for k,v in wanted.items()
                 if k in have and have[k] != v]
    if conflicts:
        raise RuntimeError('Existing Python versions differ; no changes made. Use --venv for a new environment:\n'+'\n'.join(conflicts))
    missing_python = sorted(k+'=='+v for k,v in wanted.items() if k not in have)
    print('Missing Python packages:', ', '.join(missing_python) or 'none')
    # Read-only prerequisite reporting: existing tools/services are never replaced.
    for name, local in [('go', home/'src/.tools/go/bin/go'), ('rustc', home/'src/.tools/rust/bin/rustc'), ('docker', Path('/usr/bin/docker'))]:
        found = str(local) if local.is_file() else shutil.which(name)
        print(f'Prerequisite {name}: {found or "NOT FOUND (install separately before building/deploying)"}')
    print('KVM device:', 'present' if Path('/dev/kvm').exists() else 'absent (needed for deployment)')
    if args.check:
        return 1 if missing or missing_python or not python.exists() else 0
    if missing:
        audit = subprocess.check_output(['dpkg', '--audit'], text=True).strip()
        if audit:
            raise RuntimeError('dpkg has unfinished operations; no automatic repair:\n'+audit)
        apt_env = ['env', 'DEBIAN_FRONTEND=noninteractive', 'NEEDRESTART_MODE=l', 'LC_ALL=C']
        run(sudo+apt_env+['apt-get', 'update'])
        install = ['apt-get', 'install', '-y', '--no-install-recommends', '--no-upgrade', '--no-remove']+missing
        plan = run(sudo+apt_env+['apt-get', '--simulate']+install[1:], capture=True).stdout
        # apt --no-upgrade alone can still upgrade dependencies. Reject that plan.
        unsafe = [line for line in plan.splitlines()
                  if line.startswith('Remv ') or re.match(r'^Inst \S+ \[', line)]
        if unsafe:
            raise RuntimeError('Installation would change existing packages; stopped:\n'+'\n'.join(unsafe))
        run(sudo+apt_env+install)
        left = set(PACKAGES)-installed_packages()
        if left:
            raise RuntimeError('Packages still missing: '+', '.join(sorted(left)))
    if not python.exists():
        run(user_prefix+['mkdir', '-p', str(venv.parent)])
        run(user_prefix+['python3', '-m', 'venv', str(venv)])
    if missing_python:
        # Exact pins + no-deps: cannot silently upgrade other installed packages.
        run(user_prefix+[str(python), '-m', 'pip', '--disable-pip-version-check', 'install', '--no-deps']+missing_python)
    run(user_prefix+[str(python), '-m', 'pip', '--disable-pip-version-check', 'check'])
    print('Dependencies ready; existing packages and toolchains preserved.')
    print('Bench Python:', python)
    if not args.deps_only:
        helper = Path(__file__).resolve().with_name('bench_lifecycle.py')
        command = sudo+['python3', str(helper), 'prepare', '--timeout', str(args.timeout)]
        if args.build_only:
            command.append('--build-only')
        run(command)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
