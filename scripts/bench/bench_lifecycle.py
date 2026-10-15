#!/usr/bin/env python3
"""Owned deployment lifecycle for hong's Alice bench environment."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import time
import urllib.request
import timing_patches

HERE = Path(__file__).resolve().parent
HOME = Path('/home/hong')
STATE = HOME/'src/.deployment'
ORG = HOME/'src/kuasar-sandbox'
DATA = Path('/var/lib/kuasar-hong-demo')
UNITS = {'kuasar-hong-node.service': STATE/'serve-hong-node.sh',
         'kuasar-hong-prep.service': STATE/'prep-hong-node.sh'}
REPOS = ['accelerator', 'connector', 'sandboxer', 'guest-runtime', 'orchestrator', 'kuasar-sandbox']


def run(args, user=False):
    if user:
        args = ['runuser', '-u', 'hong', '--', 'env', 'HOME=/home/hong']+list(map(str,args))
    print('+', ' '.join(map(str,args)), flush=True)
    subprocess.run(list(map(str,args)), check=True)


def units():
    present=[]
    for name, script in UNITS.items():
        path=Path('/etc/systemd/system')/name
        fragment=subprocess.check_output(['systemctl','show',name,'-p','FragmentPath','--value'],text=True).strip()
        if fragment and fragment != str(path):
            raise RuntimeError('Foreign unit location: '+fragment)
        if path.is_symlink(): raise RuntimeError('Unexpected unit symlink: '+str(path))
        if path.exists():
            text=path.read_text()
            if f'ExecStart=/bin/bash {script}\n' not in text or f'Environment=DEMO_DATA_DIR={DATA}\n' not in text:
                raise RuntimeError('Unit ownership does not match: '+name)
            if list(Path('/etc/systemd/system',name+'.d').glob('*')) or list(Path('/run/systemd/system',name+'.d').glob('*')):
                raise RuntimeError('Unit has overrides; inspect first: '+name)
            present.append(name)
    return present


def active(name):
    state=subprocess.check_output(['systemctl','show',name,'-p','ActiveState','--value'],text=True).strip()
    return state not in ('inactive','failed','')


def healthy():
    if not all(active(n) for n in UNITS): return False
    try:
        c=json.loads((STATE/'access.json').read_text())
        op=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=c['ca_file'])))
        request=urllib.request.Request(c['api_url']+'/health',headers={'Host':'api.'+c['domain'],'X-API-KEY':c['api_key']})
        with op.open(request,timeout=5) as r: return r.status==204
    except (OSError,ValueError): return False


def canonical(path):
    if path.resolve()!=path or path.is_symlink():
        raise RuntimeError('Refusing symlinked path: '+str(path))


def clean_aggregate(repo):
    """Remove generated outputs, preserving downloaded archives and checksums."""
    canonical(repo)
    binary = repo/'bin'
    build = repo/'build'
    canonical(binary)
    canonical(build)
    if binary.exists():
        shutil.rmtree(binary)
    if build.exists():
        for child in build.iterdir():
            if child.name == 'tarball':
                continue
            # Unlink generated symlinks without traversing their targets.
            if child.is_symlink() or not child.is_dir():
                child.unlink()
            else:
                shutil.rmtree(child)


def clear(deployment, build, dry):
    present=units()
    if build:
        timing_patches.plan(ORG, 'remove')  # Reject conflicting edits before stopping any service.
    if build and not deployment and any(active(n) for n in UNITS):
        raise RuntimeError('Stop/clear this deployment before removing its binaries.')
    canonical(DATA)
    if deployment and DATA.exists():
        marker=DATA/'.kuasar-demo-owner'
        if marker.is_symlink() or marker.read_text()!='kuasar-demo-owner-v1\nuid=0\ngid=0\n':
            raise RuntimeError('Demo data ownership marker does not match')
    for repo in REPOS:
        canonical(ORG/repo)
        if build and not (ORG/repo/'.git').exists(): raise RuntimeError('Missing repository: '+repo)
    print('Deployment cleanup:', deployment, '; build cleanup:', build)
    print('Preserve source, .tools, Python venv, historical bench results and native source/download caches.')
    if dry:
        print('DRY RUN: stop/remove',present if deployment else [])
        if deployment: print('DRY RUN: remove owned data',DATA,'and access/generated deployment files')
        if build:
            print('DRY RUN: make clean in',', '.join(REPOS[:-1]))
            print('DRY RUN: clean aggregate bin/build outputs; preserve build/tarball/')
        if build: timing_patches.execute(ORG, 'remove', dry=True)
        return
    if deployment:
        for name in present:
            run(['systemctl','stop',name])
            if active(name): raise RuntimeError('Unit still active: '+name)
            result=subprocess.check_output(['systemctl','show',name,'-p','Result','--value'],text=True).strip()
            if result!='success': raise RuntimeError('Cleanup did not finish successfully: '+name+' '+result)
        # Demo's EXIT hook must remove its run-owned network, units and directory.
        runs=DATA/'runs'
        if runs.exists() and any(runs.iterdir()):
            raise RuntimeError('Run state remains; preserving diagnostics instead of force-deleting: '+str(runs))
        if DATA.exists():
            for record in (DATA/'pids').glob('*.pid'):
                raise RuntimeError('PID ownership record remains: '+str(record))
            # Do not traverse a mounted filesystem, or delete data used by a live process.
            mounts=subprocess.check_output(['findmnt','-rn','-o','TARGET'],text=True).splitlines()
            if any(p==str(DATA) or p.startswith(str(DATA)+'/') for p in mounts):
                raise RuntimeError('Mount remains below deployment data')
            shutil.rmtree(DATA)
        for name in present:
            run(['systemctl','disable',name])
            (Path('/etc/systemd/system')/name).unlink()
        run(['systemctl','daemon-reload'])
        for name in ['access.json','serve-hong-node.sh','prep-hong-node.sh']:
            (STATE/name).unlink(missing_ok=True)
    if build:
        # Each component's clean target preserves native source trees containing possible WIP.
        for repo in REPOS[:-1]: run(['make','-C',ORG/repo,'clean'],user=True)
        clean_aggregate(ORG/'kuasar-sandbox')
        timing_patches.execute(ORG, 'remove')
        (STATE/'timing-build.json').unlink(missing_ok=True)
        (STATE/'build-versions.txt').unlink(missing_ok=True)
    print('Cleanup complete.')


def prepare(build_only, timeout):
    present=units()
    if present:
        if not build_only and len(present)==2 and healthy():
            expected=timing_patches.fingerprint(ORG)
            receipt=STATE/'timing-build.json'
            if expected is None or not receipt.exists() or json.loads(receipt.read_text()) != expected:
                raise RuntimeError('Existing deployment lacks a verified timing-patch build. Run clear-bench.py, then prepare-bench.py.')
            print('Existing owned timing-patched deployment is healthy; build and deployment skipped.')
            return
        raise RuntimeError('Deployment already exists but cannot be reused. Inspect it or run clear-bench.py first.')
    timing_patches.execute(ORG, 'apply')
    run(['bash',HERE/'build-official.sh'],user=True)
    run(['make','-C',ORG/'kuasar-sandbox','verify-prebuilt'],user=True)
    (STATE/'timing-build.json').write_text(json.dumps(timing_patches.fingerprint(ORG),indent=2)+'\n')
    if build_only: return
    # Old access data cannot be accepted as readiness evidence for a new deployment.
    (STATE/'access.json').unlink(missing_ok=True)
    run(['bash',HERE/'deploy-source.sh'],user=True)
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if healthy():
            print('Deployment ready. Run run-bench.py separately to benchmark.')
            return
        if not active('kuasar-hong-node.service'):
            raise RuntimeError('Node exited; inspect journalctl -u kuasar-hong-node')
        time.sleep(2)
    raise RuntimeError('Readiness timed out; services/logs preserved for diagnosis.')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['prepare','clear'])
    p.add_argument('--build-only',action='store_true')
    p.add_argument('--deployment-only',action='store_true')
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--timeout',type=int,default=600)
    a=p.parse_args()
    if os.geteuid()!=0: raise RuntimeError('Lifecycle helper requires sudo')
    if a.build_only and a.deployment_only: p.error('Choose only one scope')
    with open('/run/lock/kuasar-hong-bench.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.action=='clear': clear(not a.build_only,not a.deployment_only,a.dry_run)
        else: prepare(a.build_only,a.timeout)


if __name__=='__main__':
    try: main()
    except (RuntimeError,OSError,subprocess.CalledProcessError) as e:
        raise SystemExit(str(e))