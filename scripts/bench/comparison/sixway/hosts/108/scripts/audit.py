import json,sys,ssl,urllib.request,subprocess as sp
from pathlib import Path
m=Path('/opt/bench108');cfg=json.loads((m/'deploy/startup.json').read_text());name=sys.argv[1];c=cfg[name]
if name=='kuasar-mlink':
 d=json.load(urllib.request.urlopen('http://127.0.0.1:28082/internal/status'));assert d['thinkactors']==0 and d['operations']==0 and d['capacity']['assigned']==0;out=dict(success=True,capacity=d['capacity'],thinkactors=d['thinkactors'],operations=d['operations'])
elif name=='kuasar-fork':
 req=urllib.request.Request(c['api_url']+'/template-pool',headers={'X-API-Key':Path(c['key_file']).read_text().strip()});d=json.load(urllib.request.urlopen(req));assert d['assigned']==0 and d['ready']==64 and d['owned']==64
 out=dict(success=True,pool=d)
else:
 req=urllib.request.Request(c['api_url']+'/v2/sandboxes',headers={'X-API-Key':Path(c['key_file']).read_text().strip()});ctx=ssl.create_default_context(cafile=c['ca_file']) if c.get('ca_file') else None
 d=json.load(urllib.request.urlopen(req,context=ctx,timeout=10))
 rows=d if isinstance(d,list) else d.get('sandboxes',d.get('items',None));assert rows==[],d
 out=dict(success=True,sandboxes=rows)
 if name=='kuasar-fork':
  req=urllib.request.Request(c['api_url']+'/template-pool',headers={'X-API-Key':Path(c['key_file']).read_text().strip()});out['pool']=json.load(urllib.request.urlopen(req));assert out['pool']['assigned']==0 and out['pool']['ready']==64
(m/'results'/('audit-'+name+'.json')).write_text(json.dumps(out,indent=2));print(name,'CLEAN')
