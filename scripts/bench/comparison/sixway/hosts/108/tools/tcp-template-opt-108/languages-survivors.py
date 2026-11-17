import os,json,urllib.request,shlex,uuid
from pathlib import Path
M=Path('/opt/bench108');url='http://127.0.0.1:18887';key=(M/'deploy/fork/api-key').read_text().strip();os.environ.update(E2B_API_KEY=key,E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
from e2b import Sandbox
out={}
for name in ['node','ruby']:
 for first in ['parent','child']:
  p=Sandbox.create(name,timeout=120);c=None
  def check(s):
   marker=uuid.uuid4().hex
   argv=['exec','/usr/local/bin/node','-e','console.log(process.argv[1])',marker] if name=='node' else ['exec','/usr/local/bin/ruby','-e','$stdout.sync=true; puts ARGV[0]',marker]
   r=s.commands.run(shlex.join(argv),user='root',timeout=30);assert r.exit_code==0 and r.stdout.strip()==marker
  try:
   req=urllib.request.Request(url+'/sandboxes/'+p.sandbox_id+'/fork',data=b'{"timeout":120}',headers={'X-API-Key':key,'Content-Type':'application/json'})
   d=json.load(urllib.request.urlopen(req,timeout=180))[0]['sandbox'];c=Sandbox.connect(d['sandboxID'])
   check(p);check(c)
   if first=='parent':p.kill();p=None;check(c)
   else:c.kill();c=None;check(p)
   out[name+'-'+first+'-first']={'both_interpreters_executed':True,'survivor_interpreter_executed':True}
  finally:
   if c:c.kill()
   if p:p.kill()
(M/'results/tcp-template-opt-108/languages-survivors.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
