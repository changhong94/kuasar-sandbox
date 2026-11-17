import json,sys,os,shlex,time
from pathlib import Path
M=Path('/opt/bench108');url='http://127.0.0.1:18887';os.environ.update(E2B_API_KEY=(M/'deploy/fork/api-key').read_text().strip(),E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
from e2b import Sandbox
out={}
for lang in ['node','ruby']:
 cfg=json.loads((M/'tools/tcp-template-opt-108'/f'{lang}.json').read_text());start=time.perf_counter_ns();s=Sandbox.create(lang,timeout=120);created=time.perf_counter_ns()
 try:
  command='cd /; '+shlex.join(['exec','/usr/bin/env','-i',*cfg['_env'],cfg['_binary'],cfg['_flag'],cfg['_code'],'READY_DIAGNOSTIC'])
  z=s.commands.run(command,user='root');assert z.stdout.strip()=='READY_DIAGNOSTIC';out[lang]={'sid':s.sandbox_id,'create_ms':(created-start)/1e6,'completion_ms':(time.perf_counter_ns()-start)/1e6}
 finally:s.kill()
(M/'results/five-rounds-108/round5'/f'{sys.argv[1]}-diagnostic.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
