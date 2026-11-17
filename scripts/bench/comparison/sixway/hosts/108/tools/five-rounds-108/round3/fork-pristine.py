import json,sys,importlib.util
from pathlib import Path
M=Path('/opt/bench108');T=M/'tools/five-rounds-108/round3';R=M/'results/five-rounds-108/round3';spec=importlib.util.spec_from_file_location('bench',T/'bench.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);out={}
for name in ['node','ruby']:
 cfg=json.loads((T/(name+'.json')).read_text());c,Sandbox=b.setup('kuasar-fork',cfg);s=Sandbox.create(name,timeout=120)
 try:
  z=s.commands.run('fincore --bytes --noheadings --output RES /usr/local/bin/'+name,user='root');assert z.exit_code==0 and int(z.stdout.strip())>=0
  procs=s.commands.run('for f in /proc/[0-9]*/comm; do cat "$f" 2>/dev/null; done',user='root').stdout.splitlines();assert name not in procs
  out[name]={'no_interpreter_running':True,'executable_resident_bytes':int(z.stdout.strip()),'template':name}
 finally:s.kill()
(R/'fork-pristine.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
