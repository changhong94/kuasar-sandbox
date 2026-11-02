"""Reproducible three-product performance pilot. No model calls or service edits.

One worker per product avoids E2B environment-variable cross-contamination.
Smoke is deliberately small and explicitly not a statistically valid ranking.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('--workspace',default='/home/hong/src/.deployment/skyrl-rollout')
p.add_argument('--config',default='/home/hong/src/.comparison/suite-config.json')
p.add_argument('--output',required=True)
p.add_argument('--profile',choices=['smoke','extended'],default='smoke')
p.add_argument('--products',nargs='+',choices=['kuasar','cube','agentenv'],default=['kuasar','cube','agentenv'])
p.add_argument('--cases',nargs='+',default=['certificate','runtime','memory','resume','density','storage','pressure','recovery'])
p.add_argument('--isolated-host-confirmed',action='store_true')
a=p.parse_args();W=Path(a.workspace);D=Path(a.output);D.mkdir(parents=True,exist_ok=False)
if a.profile=='extended' and not a.isolated_host_confirmed:p.error('Extended load requires an exclusive test window (--isolated-host-confirmed)')
lock=open('/run/skyrl-threeway-benchmark.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
plan=[];rounds=1 if a.profile=='smoke' else 3
for r in range(rounds):
    products=a.products[r%len(a.products):]+a.products[:r%len(a.products)]
    for case in a.cases:
        if case not in ('certificate','runtime','memory','resume','density','storage','pressure','recovery'):p.error('Unknown case '+case)
        variants=[{}]
        if case=='certificate':variants=[dict(mode='separate'),dict(mode='batch')]
        if case=='density':variants=[dict(count=n) for n in ([1,2] if a.profile=='smoke' else [1,4,8])]
        if case=='storage':variants=[dict(entropy=e,different=d,count=2) for e in ('low','high') for d in (False,True)]
        if case=='pressure':variants=([dict(rate=0,limit=2,requests=4),dict(rate=1,limit=2,requests=4)] if a.profile=='smoke' else
            [dict(rate=rate,limit=8,requests=60 if rate==0 else int(60*rate)) for rate in (0,1,2,5)])
        if case=='recovery':variants=[dict(rate=2,limit=2 if a.profile=='smoke' else 8,requests=4 if a.profile=='smoke' else 20)]
        for v in variants:
            for product in products:plan.append(dict(round=r,case=case,product=product,**v))
(D/'plan.json').write_text(json.dumps(dict(profile=a.profile,trials=plan,formal_ranking=False,
    constraints=['Kuasar prefetch off','original TB2 scoring unchanged','no model calls','no global cache flush','no service restart','only owned sandboxes deleted'],
    deferred=[dict(test='host-cold startup / service prewarming ablation',reason='Requires exclusive services, source-to-release mapping and verified cache controls; not equivalent to guest file DONTNEED'),
              dict(test='fresh template import cost',reason='Existing pinned templates reused; provisioning not timed retrospectively'),
              dict(test='native overhead ratio',reason='Requires matching native interpreter/libraries/CPU placement before claiming ratio'),
              dict(test='independent exported snapshot retention',reason='Current new test uses API pause storage; existing Kuasar/Cube extent suite remains separate')]),indent=2))
(D/'sources').mkdir()
hashes={}
for source in [*HERE.glob('*.py'),HERE.parent/'extent_accounting.py']:
    data=source.read_bytes();(D/'sources'/source.name).write_bytes(data);hashes[source.name]=hashlib.sha256(data).hexdigest()
(D/'source-hashes.json').write_text(json.dumps(hashes,indent=2))
workspace_sources=['run_fixed_certificate.py','fixed_certificate_agent.py','certificate-replay-commands-v1.json',
    'offline_replay_env.py','formal_instrumentation.py','prepared_openssl_env.py','unified_python_env.py','skyrl_threeway_env.py']
(D/'workspace-sources').mkdir();workspace_hashes={}
for name in workspace_sources:
    data=(W/name).read_bytes();(D/'workspace-sources'/name).write_bytes(data);workspace_hashes[name]=hashlib.sha256(data).hexdigest()
(D/'workspace-source-hashes.json').write_text(json.dumps(workspace_hashes,indent=2))
for name in ('source-checkouts.json','source-map.json'):
    if (HERE/name).exists():shutil.copy2(HERE/name,D/name)
driver=(W/'run_fixed_certificate.py').read_text()
old="'fixed_certificate_agent:FixedCertificateAgent'"
assert driver.count(old)==1
driver=driver.replace(old,"'certificate_agent:PerformanceCertificateAgent'")
# The cloned driver expects fixture/helper modules beside itself. Preserve its
# workspace anchor rather than copying credentials or altering the old runner.
driver=driver.replace('W=Path(__file__).resolve().parent','W=Path('+repr(str(W))+')')
(D/'certificate_driver.py').write_text(driver)
env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(D/'sources'),str(W),'/home/hong/src/.deployment/terminal-bench-pilot']),PERF_WORKSPACE=str(W))
results=[]
for index,item in enumerate(plan):
    for name,digest in workspace_hashes.items():
        if hashlib.sha256((W/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Dependency source changed mid-run: '+name)
    name=f"{index:03d}-{item['case']}-{item['product']}";out=D/name
    print('START '+name,flush=True)
    (D/'progress.json').write_text(json.dumps(dict(index=index,total=len(plan),current=name,completed=results),indent=2))
    childenv=dict(env,FORMAL_RUN_DIR=str(out),PERF_CERT_MODE=item.get('mode','separate'))
    if item['case']=='certificate':
        cmd=[sys.executable,str(D/'certificate_driver.py'),item['product'],'openssl-selfsigned-cert','--output',str(out),'--oracle','--prepared-openssl']
    else:
        cmd=[sys.executable,str(D/'sources'/'worker.py'),'--workspace',str(W),'--config',a.config,'--product',item['product'],'--output',str(out),'--case',item['case']]
        for key in ('count','rate','limit','requests','entropy'):
            if key in item:cmd += ['--'+key,str(item[key])]
        if item.get('different'):cmd+=['--different']
        if item['case'] in ('memory','density','storage','pressure','recovery'):cmd+=['--sample']
    t=time.monotonic()
    with (D/(name+'.log')).open('w') as log:
        proc=None
        try:
            proc=subprocess.Popen(cmd,env=childenv,stdout=log,stderr=subprocess.STDOUT)
            proc.wait(timeout=900)
            row=dict(item,name=name,returncode=proc.returncode,seconds=time.monotonic()-t)
        except subprocess.TimeoutExpired:
            # Do not proceed to higher load after a worker timeout. Its ledger
            # remains available for targeted cleanup; never mass-delete.
            proc.terminate()
            try:proc.wait(timeout=60)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            row=dict(item,name=name,returncode=124,seconds=time.monotonic()-t,error='worker_timeout')
    if item['case']=='certificate' and row['returncode']==0:
        tr=list(out.glob('trials/*/result.json'))
        row['reward']=(json.loads(tr[0].read_text()).get('verifier_result') or {}).get('rewards',{}).get('reward') if len(tr)==1 else None
        if row['reward']!=1:row.update(returncode=1,error='original_verifier_failed')
    results.append(row);(D/'results.json').write_text(json.dumps(results,indent=2));print('END '+json.dumps(row),flush=True)
    if row['returncode']:
        (D/'blocked.json').write_text(json.dumps(row,indent=2));break
else:(D/'complete.json').write_text(json.dumps(dict(time=time.time(),runs=len(results))))
subprocess.run([sys.executable,str(D/'sources'/'summarize.py'),str(D)],check=True)
subprocess.run([sys.executable,str(D/'sources'/'validate.py'),str(D)],check=True)
if any(r['returncode'] for r in results):sys.exit(1)
