"""Read-only readiness gates. Never warm guest Python or clear host caches."""
import json,time,urllib.request
from pathlib import Path
def wait(c,capacity=64,timeout=180,allow_surplus=False):
 start=time.monotonic_ns();polls=0;last=None
 if c.get('pool_kind') not in ('fork','mlink'):
  return dict(supported=False,elapsed_ms=0,state=None,reason='product exposes no equivalent pool readiness API; not asserted ready')
 while (time.monotonic_ns()-start)/1e9<timeout:
  polls+=1
  try:
   if c['pool_kind']=='fork':
    req=urllib.request.Request(c['api_url']+'/template-pool',headers={'X-API-Key':Path(c['key_file']).read_text().strip()})
    with urllib.request.urlopen(req,timeout=3) as f:last=json.load(f)
    ok=last.get('ready')==capacity and last.get('assigned')==0 and last.get('preparing',0)==0
   else:
    with urllib.request.urlopen(c.get('pool_status_url','http://127.0.0.1:29082/internal/status'),timeout=3) as f:last=json.load(f)
    cap=last['capacity'];prep=last['preparation'];tpl=next(x for x in last['templates'] if x['id']==c['template'])
    ok=(all(cap.get(k,0)==0 for k in ('assigned','waiters','preparing','rearming','recycling','retiring','failed')) and cap['configured']==c.get('pool_total_capacity',capacity) and (cap['ready']>=capacity if allow_surplus else cap['ready']==capacity) and (prep['profiles'].get('profile:2:2048',0)>=capacity if allow_surplus else prep['profiles'].get('profile:2:2048')==capacity) and prep.get('l3',0)==0 and prep.get('l3_preparing',0)==0 and tpl['storage_ready']>=capacity and tpl['storage_warming']==0 and tpl['memory_cache']['full'])
   if ok:return dict(supported=True,elapsed_ms=(time.monotonic_ns()-start)/1e6,polls=polls,state=last)
  except (OSError,KeyError,StopIteration) as e:last={'error':repr(e)}
  time.sleep(.05)
 raise TimeoutError(('pool readiness',last))
