import json,subprocess,time,urllib.request
from pathlib import Path
def select(c,templates):
 # Runtime L2 pool stays at 64 / 8 preparers. hot-ready-workers is an L3
 # per-image VM reservation count, not the generic preparation concurrency.
 t=time.monotonic_ns();actions=[]
 for template in templates:
  if template==c['template']:continue
  z=subprocess.run(c['ctl']+['template','prewarm','set',template,'--memory-state','disabled','--storage-min-ready','0','--storage-ready','0','--hot-ready-workers','0','--wait'],capture_output=True,text=True)
  if z.returncode:raise RuntimeError(z.stderr[-1000:])
  actions.append({'template':template,'mode':'disabled'})
 z=subprocess.run(c['ctl']+['template','prewarm','set',c['template'],'--memory-state','full','--storage-min-ready','64','--storage-ready','64','--hot-ready-workers','0','--wait'],capture_output=True,text=True)
 if z.returncode:raise RuntimeError(z.stderr[-1000:])
 d=dict(selected=c['template'],actions=actions,elapsed_ms=(time.monotonic_ns()-t)/1e6)
 root=Path('/home/hong/codex-work/sevenway-fresh-181/preparation/mlink-select');root.mkdir(parents=True,exist_ok=True);(root/(str(time.time_ns())+'.json')).write_text(json.dumps(d,indent=2))
 return d
if __name__=='__main__':
 import sys
 cfg=json.load(open('/home/hong/codex-work/sevenway-fresh-181/tools/config.json'));c=cfg['kuasar-mlink'];c['template']=cfg['_languages'][sys.argv[1]]['templates']['kuasar-mlink'];select(c,[v['templates']['kuasar-mlink']for v in cfg['_languages'].values()])
