import json,subprocess,time
from pathlib import Path
M=Path('/opt/bench108');R=M/'results/language-matched-108';cfg=json.loads((M/'tools/python-matched-audit-108/config.json').read_text());ctl=[x.replace('/data/mlink/', '/data/mlink-lang/') for x in cfg['kuasar-mlink']['ctl']];cat=json.loads((M/'deploy/fork/images.json').read_text());out={}
for name in ['node','ruby']:
 start=time.perf_counter_ns()
 p=subprocess.run(ctl+['template','import',cat[name]['disk'],'--name','language-matched-108-'+name,'--cpu-count','1','--memory-mb','2048','--disk-size-mb','1024','--scope','full'],capture_output=True,text=True)
 (R/(name+'-import.stdout')).write_text(p.stdout);(R/(name+'-import.stderr')).write_text(p.stderr)
 assert p.returncode==0,(p.returncode,p.stderr)
 template=p.stdout.strip();assert template.startswith('snap_'),template
 out[name]={'template':template,'import_ms':(time.perf_counter_ns()-start)/1e6,'image':cat[name]};(R/'mlink-import.json').write_text(json.dumps(out,indent=2));print(name,template,flush=True)
