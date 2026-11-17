#!/usr/bin/python3
"""Private benchmark daemon runtime: host-network containers join its owned netns."""
import os,sys,json,tempfile
from pathlib import Path
args=sys.argv[1:]
if 'create' in args or 'run' in args:
 bundle=None
 for i,a in enumerate(args):
  if a in ('--bundle','-b'):bundle=Path(args[i+1])
  elif a.startswith('--bundle='):bundle=Path(a.split('=',1)[1])
 if bundle is None:bundle=Path.cwd()
 real=str(bundle.resolve())
 if not (real.startswith('/run/bench108-cube-docker/') or real.startswith('/run/containerd/io.containerd.runtime.v2.task/bench108-cube/')):
  raise SystemExit('refusing non-benchmark OCI bundle: '+real)
 p=bundle/'config.json';d=json.loads(p.read_text());ns=d.setdefault('linux',{}).setdefault('namespaces',[])
 if not any(n['type']=='network' for n in ns):
  ns.append({'type':'network','path':'/run/netns/b108-cube'})
  fd,tmp=tempfile.mkstemp(prefix='.bench108-',dir=bundle)
  with os.fdopen(fd,'w') as f:json.dump(d,f)
  os.chmod(tmp,p.stat().st_mode&0o777);os.replace(tmp,p)
os.execv('/usr/bin/runc',['runc',*args])
