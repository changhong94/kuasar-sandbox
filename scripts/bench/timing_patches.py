"""Preflight both timing patches before changing source; never reset user changes."""
import hashlib
import os
import pwd
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
PATCHES={
 'orchestrator':[HERE/'patches/orchestrator-timing.patch',HERE/'patches/orchestrator-timing-uncommented.patch',HERE/'orchestrator-fac2b6a8712f.patch'],
 'sandboxer':[HERE/'patches/sandboxer-timing.patch',HERE/'patches/sandboxer-timing-uncommented.patch',HERE/'sandboxer-b1db083dee2c.patch'],
}


def git(repo,patch,reverse=False,check=False):
    command=['git','-C',str(repo),'apply']
    if reverse: command.append('--reverse')
    if check: command.append('--check')
    command.append(str(patch))
    if os.geteuid()==0:
        owner=pwd.getpwuid(repo.stat().st_uid).pw_name
        command=['runuser','-u',owner,'--']+command
    return subprocess.run(command,capture_output=True,text=True)


def plan(org,action):
    result=[]
    for name,candidates in PATCHES.items():
        repo=org/name
        # A successful reverse check proves the patch is already present.
        applied=next((p for p in candidates if git(repo,p,True,True).returncode==0),None)
        available=next((p for p in candidates if git(repo,p,False,True).returncode==0),None) if applied is None else None
        if applied is None and available is None:
            raise RuntimeError(f'{name}: timing patch conflicts or is partially applied; source preserved. Resolve manually, then retry.')
        chosen=applied or available
        change=(action=='apply' and applied is None) or (action=='remove' and applied is not None)
        result.append((repo,chosen,change,applied is not None))
    return result


def fingerprint(org):
    state=plan(org,'apply')
    if not all(item[3] for item in state): return None
    return {repo.name:hashlib.sha256(patch.read_bytes()).hexdigest() for repo,patch,_,_ in state}


def execute(org,action,dry=False):
    items=plan(org,action)
    changed=[]
    try:
        for repo,patch,change,applied in items:
            print(f'{repo.name}: {action if change else "skip (already in requested state)"} {patch.name}',flush=True)
            if not change or dry: continue
            response=git(repo,patch,reverse=action=='remove')
            if response.returncode: raise RuntimeError(response.stderr.strip())
            changed.append((repo,patch))
    except Exception:
        for repo,patch in reversed(changed):
            rollback=git(repo,patch,reverse=action=='apply')
            if rollback.returncode:
                raise RuntimeError('Patch rollback failed; inspect '+str(repo)+': '+rollback.stderr)
        raise