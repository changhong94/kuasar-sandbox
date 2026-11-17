import sys,json,subprocess as s
from pathlib import Path
B=Path('/home/hong/src/research/sixway-languages-20261117');sys.path.insert(0,str(B/'tools'));import startup
n=sys.argv[1];config=json.loads((B/'tools/config.json').read_text());c,S=startup.setup(n,config)
if n=='kuasar-fork':
 import urllib.request
 req=urllib.request.Request(c['api_url']+'/template-pool',headers={'X-API-Key':Path(c['key_file']).read_text().strip()});data=json.load(urllib.request.urlopen(req));assert data['assigned']==0 and data['preparing']==False,data
elif n=='kuasar-mlink':
 data=json.loads(s.check_output(c['ctl']+['list','--json'],text=True));assert not data,data
else:
 pager=S.list();data=[]
 while pager.has_next:data.extend(x.sandbox_id for x in pager.next_items())
 assert not data,(n,data)
(B/'results'/('inventory-after-'+n+'.json')).write_text(json.dumps(data,indent=2));print(n,'unassigned',flush=True)
