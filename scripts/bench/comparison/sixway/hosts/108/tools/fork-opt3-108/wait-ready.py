import urllib.request,json,time
from pathlib import Path
for _ in range(300):
 try:
  key=Path('/opt/bench108/deploy/fork/api-key').read_text().strip()
  req=urllib.request.Request('http://127.0.0.1:18887/template-pool',headers={'X-API-Key':key})
  d=json.load(urllib.request.urlopen(req,timeout=2))
  if d['ready']==64 and d['assigned']==0:
   print(json.dumps(d));break
 except OSError: pass
 time.sleep(.2)
else:raise RuntimeError('pool not ready')
