#!/usr/bin/env python3
"""Write scoped configuration for the existing five-product deployment.

Run on 10.213.17.113, not on a fresh host. Default: read-only plan.
Usage: sudo python3 write_sandbox_configs.py --apply
This file does not restart services. Existing credentials and binaries are kept.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import tomllib

# Section 1: Deployment paths and shared helpers.
HOME = Path('/home/hong')
DEPLOY = HOME / 'deploy/comparison'
PRIVATE = HOME / 'deploy/private-pilot'
PRODUCTS = ('kuasar-off', 'cube', 'agentenv', 'kuasar-uffd', 'kuasar-mlink')
NAMESPACES = dict(zip(PRODUCTS, ('bench113', 'bench113', 'bench113', 'bench113-u', 'bench113-m')))
BACKUPS = HOME / 'results' / ('configuration-' + time.strftime('%Y%m%d_%H%M%S'))

def run(args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, text=True, capture_output=True, **kwargs).stdout

def lock():
    handle = open('/run/skyrl-threeway-benchmark.lock', 'a')
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle

def write(path, text, apply=False, mode=0o600):
    path = Path(path)
    if path.exists() and path.read_text() == text:
        print('UNCHANGED', path)
        return False
    print('WRITE' if apply else 'WOULD WRITE', path)
    if not apply:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    st = path.stat() if path.exists() else None
    if st:
        backup = BACKUPS / path.relative_to('/')
        backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copy2(path, backup)
        backup.chmod(0o600)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, st.st_mode & 0o777 if st else mode)
        if st:
            os.chown(tmp, st.st_uid, st.st_gid)
            # Preserve SELinux labels and other extended attributes on this host.
            for attribute in os.listxattr(path):
                os.setxattr(tmp, attribute, os.getxattr(path, attribute))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True

def replace_one(text, pattern, replacement):
    result, count = re.subn(pattern, replacement, text, flags=re.M)
    if count != 1:
        raise RuntimeError(f'Expected exactly one match: {pattern}; found {count}')
    return result

def access(product):
    base = DEPLOY / 'kuasar-state' if product == 'kuasar-off' else PRIVATE / 'uffd-state'
    return json.loads((base / 'access.json').read_text())

def require_idle(product):
    # The status probe is local to an isolated namespace. It permits an expired
    # test certificate only to determine whether a safe certificate repair is possible.
    if product == 'kuasar-mlink':
        data = json.loads(run(['nsenter', '--net=/run/netns/bench113-m', 'curl',
                              '-fsS', '--max-time', '10', 'http://127.0.0.1:28082/internal/status']))
        if data['thinkactors'] or data['operations'] or data['capacity']['assigned']:
            raise RuntimeError('mlink is busy; no service changes were authorized for active instances')
        return
    if product in ('kuasar-off', 'kuasar-uffd'):
        c = access(product)
    elif product == 'cube':
        import shlex
        env = dict(line.split('=', 1) for line in Path('/usr/local/services/cubetoolbox/.one-click.env').read_text().splitlines()
                   if line.startswith(('CUBE_API_KEY=', 'CUBE_API_SANDBOX_DOMAIN=')))
        c = {'api_url': 'http://127.0.0.1:3000', 'api_key': shlex.split(env['CUBE_API_KEY'])[0],
             'domain': shlex.split(env['CUBE_API_SANDBOX_DOMAIN'])[0]}
    elif product == 'agentenv':
        c = {'api_url': 'http://127.0.0.1:18000',
             'api_key': (HOME / 'data/comparison/agentenv/secrets/api-key').read_text().strip(),
             'domain': 'localhost'}
    else:
        raise ValueError(product)
    data = json.loads(run(['nsenter', '--net=/run/netns/' + NAMESPACES[product], 'curl',
                           '-kfSs', '--max-time', '10', '--noproxy', '*', '-H', 'X-API-KEY: ' + c['api_key'],
                           '-H', 'Host: api.' + c['domain'], c['api_url'] + '/v2/sandboxes']))
    if data != []:
        raise RuntimeError(product + ' has existing instances; refusing to restart it')

# Section 2: Kuasar off and UFFD resource configuration.
def configure_kuasar(product, apply):
    c = access(product)
    path = Path(c['work_dir']) / 'conductor.yaml'
    text = path.read_text()
    # Only the sandbox resource defaults are changed, not builder resources.
    start = text.index('sandbox:')
    end = text.index('  boot:', start)
    section = text[start:end]
    for field in ('capacity', 'allocatable'):
        section = replace_one(section, r'(' + field + r':\s*\{\s*cpu:)\s*\d+(,\s*memory:)\s*[^}]+}',
                              r'\g<1> 1\g<2> 2GiB }')
    write(path, text[:start] + section + text[end:], apply)
    # Prefetch is a per-create request setting, not a conductor global flag.
    return {'access_file': str((DEPLOY / 'kuasar-state' if product == 'kuasar-off' else PRIVATE / 'uffd-state') / 'access.json'),
            'cpu': 1, 'memory_mib': 2048, 'restore_metadata': {'kuasar-sandbox.restore': '{"prefetch":"off"}'}}

# Section 3: CubeSandbox network configuration.
def configure_cube(apply):
    root = Path('/usr/local/services/cubetoolbox')
    for path, pattern, replacement in (
        (root / '.one-click.env', r'^CUBE_SANDBOX_ETH_NAME=.*$', 'CUBE_SANDBOX_ETH_NAME=bdns-guest'),
        (root / 'Cubelet/config/config.toml', r'^\s*eth_name\s*=.*$', '    eth_name = "bdns-guest"')):
        write(path, replace_one(path.read_text(), pattern, replacement), apply)
    # Existing templates retain their resource definition; this script does not rebuild them.
    return {'api_url': 'http://127.0.0.1:3000', 'egress_interface': 'bdns-guest',
            'template_record': str(HOME / 'logs/comparison/cube-template.log'), 'expected_cpu': 1, 'expected_memory_mib': 2048}

# Section 4: AgentENV configuration; preserve its existing reclaim policy.
def configure_agentenv(apply):
    path = HOME / 'data/comparison/agentenv/config/config.toml'
    text = path.read_text()
    for key, value in [('home_path', str(HOME / 'data/comparison/agentenv')),
                       ('runtime_path', '/run/agentenv-comparison'), ('virtualization_mode', 'kvm')]:
        text = replace_one(text, r'^' + key + r'\s*=.*$', key + ' = ' + json.dumps(value))
    tomllib.loads(text)
    write(path, text, apply)
    return {'api_url': 'http://127.0.0.1:18000', 'template': 'comparison-python',
            'config_file': str(path), 'expected_cpu': 1, 'expected_memory_mib': 2048}

# Section 5: mlink pool and cleanup configuration; never modify opaque binaries.
def configure_mlink(apply):
    path = PRIVATE / 'mlink-private-start.sh'
    text = replace_one(path.read_text(), r'write_node_configs\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+',
                       'write_node_configs 64 1000 2 2 64')
    # The generated configuration is patched before ttlet starts, so the cleanup
    # limit also survives a restart if the upstream helper changes its default.
    marker = '# Enforce the comparison cleanup limit after configuration generation.'
    if marker not in text:
        text = text.replace('write_node_configs 64 1000 2 2 64',
            'write_node_configs 64 1000 2 2 64\n' + marker + '\n' +
            "sed -i -E 's/^cleanup_concurrency[[:space:]]*=.*/cleanup_concurrency = 16/' \"$work/ttlet.toml\"")
    write(path, text, apply)
    path = HOME / 'data/mlink3/ttlet.toml'
    text = path.read_text()
    for key, value in [('foreground_quiet_period_ms', 1000), ('cleanup_concurrency', 16)]:
        text = replace_one(text, r'^' + key + r'\s*=.*$', f'{key} = {value}')
    tomllib.loads(text)
    write(path, text, apply)
    return {'api_url': 'http://127.0.0.1:28080', 'data_url': 'http://127.0.0.1:28081',
            'admin_url': 'http://127.0.0.1:28082', 'ready_slots': 64,
            'quiet_period_ms': 1000, 'cleanup_concurrency': 16, 'cpu': 1, 'memory_mib': 2048}

# Section 6: Write a credential-free benchmark configuration manifest.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo; even planning reads protected deployment files.')
    held_lock = lock()
    manifest = {}
    for product in ('kuasar-off', 'kuasar-uffd'):
        manifest[product] = configure_kuasar(product, args.apply)
    manifest['cube'] = configure_cube(args.apply)
    manifest['agentenv'] = configure_agentenv(args.apply)
    manifest['kuasar-mlink'] = configure_mlink(args.apply)
    write(DEPLOY / 'fiveway/configuration.json', json.dumps(manifest, indent=2) + '\n', args.apply)
    print('No services restarted. Run repair_deployment.py to apply scoped runtime repairs.')

if __name__ == '__main__':
    main()
