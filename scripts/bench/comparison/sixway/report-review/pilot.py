from pathlib import Path
import json,sys,uuid,time,fcntl,subprocess
B=Path('/home/hong/src/research/report-review-113');sys.path.insert(0,str(B/'tools'))
from startup import setup
from languages import select_language
p=sys.argv[1];c,S=setup(p,select_language(json.loads((B/'tools/config.json').read_text()),'python'));s=None;r={'product':p,'success':False}
try:
 start=time.monotonic_ns();s=S.create(c['template'],timeout=300,request_timeout=120,**c.get('create_kwargs',{}));r['id']=s.sandbox_id;(B/('pilot-'+p+'.json')).write_text(json.dumps(r))
 m=uuid.uuid4().hex;x=s.commands.run('/usr/local/bin/python3 -c "print(\''+m+'\',flush=True)"',user='root',timeout=90);assert x.exit_code==0 and m in x.stdout,(x.exit_code,x.stderr)
 r.update(success=True,print_ms=(time.monotonic_ns()-start)/1e6)
finally:
 if s:s.kill(request_timeout=120);r['destroyed']=True
 (B/('pilot-'+p+'.json')).write_text(json.dumps(r,indent=2))
print(json.dumps(r))
