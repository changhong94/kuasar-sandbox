import os,json,time,shlex,uuid
from pathlib import Path
M=Path('/opt/bench108');url='http://127.0.0.1:18887';os.environ.update(E2B_API_KEY=(M/'deploy/fork/api-key').read_text().strip(),E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
from e2b import Sandbox
out={}
for lang in ['node','ruby']:
 cfg=json.loads((M/'tools/tcp-template-opt-108'/f'{lang}.json').read_text());s=Sandbox.create(lang,timeout=120);a=[]
 try:
  for kind in ['first','repeat']:
   marker='DIAG_'+uuid.uuid4().hex;command='cd /; '+shlex.join(['exec','/usr/bin/env','-i',*cfg['_env'],cfg['_binary'],cfg['_flag'],cfg['_code'],marker]);receipt=[];buf=[]
   def got(x):
    buf.append(x)
    if not receipt and marker+'\n' in ''.join(buf):receipt.append(time.perf_counter_ns())
   start=time.perf_counter_ns();z=s.commands.run(command,user='root',on_stdout=got);assert z.stdout.strip()==marker and receipt
   a.append({'kind':kind,'exec_to_print_ms':(receipt[0]-start)/1e6})
  out[lang]=a
 finally:s.kill()
(M/'results/restore-exec-opt-108/cold-warm-diagnostic.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
