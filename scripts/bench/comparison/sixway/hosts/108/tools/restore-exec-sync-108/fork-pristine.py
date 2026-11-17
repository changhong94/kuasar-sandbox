import json,sys,importlib.util
from pathlib import Path
M=Path('/opt/bench108');T=M/'tools/restore-exec-sync-108';R=M/'results/restore-exec-sync-108';spec=importlib.util.spec_from_file_location('bench',T/'bench.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);out={}
for name in ['node','ruby']:
 cfg=json.loads((T/(name+'.json')).read_text());c,Sandbox=b.setup('kuasar-fork',cfg);s=Sandbox.create(name,timeout=120)
 try:
  z=s.commands.run('fincore --bytes --noheadings --output RES /usr/local/bin/'+name,user='root');assert z.exit_code==0 and int(z.stdout.strip())==0
  out[name]={'executable_resident_bytes':0,'template':name}
 finally:s.kill()
(R/'fork-pristine.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
