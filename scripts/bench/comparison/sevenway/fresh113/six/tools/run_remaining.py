from pathlib import Path
import subprocess as sp,sys,time,json,os
B=Path('/home/hong/src/research/sixway-aligned-20261117');T=B/'tools';R=B/'results'
def run(n,args):
 t=time.monotonic()
 with (R/(n+'.log')).open('w') as f:r=sp.run(list(map(str,args)),stdout=f,stderr=sp.STDOUT)
 if r.returncode:raise RuntimeError((n,r.returncode))
 return (time.monotonic()-t)*1000
assert (R/'startup/summary.json').exists()
run('enrich',[sys.executable,T/'enrich.py'])
run('expand-resource',[sys.executable,T/'expand_resource_profile.py'])
t=time.monotonic();run('wait-resource-fork',['nsenter','--net=/run/netns/py113-fork',sys.executable,'/home/hong/src/research/python-latest-113/tools/wait-ready.py'])
cfg=json.loads((T/'config.json').read_text());ctl=['nsenter','--net=/run/netns/bench113-m-generic']+cfg['kuasar-mlink']['ctl'];ctl[-1]='300'
run('warm-resource-mlink',ctl+['template','prewarm','set',cfg['kuasar-mlink']['template'],'--memory-state','full','--storage-min-ready','64','--storage-ready','64','--hot-ready-workers','0','--wait'])
(R/'resource-readiness.json').write_text(json.dumps(dict(elapsed_ms=(time.monotonic()-t)*1000,capacity=64),indent=2))
run('full-run',[sys.executable,T/'run_full.py'])
run('audit',[sys.executable,T/'final_audit.py'])
print('ALL COMPLETE',flush=True)
