import subprocess,json,time
from pathlib import Path
M=Path('/opt/bench108');R=M/'results/five-rounds-108/round1';d=json.loads((R/'mlink-import.json').read_text());ctl=json.loads((M/'tools/python-matched-audit-108/config.json').read_text())['kuasar-mlink']['ctl'];ctl=[x.replace('/data/mlink/', '/data/mlink-lang/') for x in ctl];out={}
import sys
for name in sys.argv[1:]:
 v=d[name]
 start=time.perf_counter_ns();z=subprocess.run(ctl+['template','prewarm','set',v['template'],'--memory-state','full','--hot-ready-workers','0','--storage-min-ready','64','--storage-ready','64','--wait'],capture_output=True,text=True);assert z.returncode==0,z.stderr
 status=json.loads(subprocess.check_output(ctl+['template','prewarm','inspect',v['template']],text=True));out[name]={'elapsed_ms':(time.perf_counter_ns()-start)/1e6,'status':status};print(name,out[name]['elapsed_ms'],flush=True)
(R/('mlink-preparation-'+name+'.json')).write_text(json.dumps(out,indent=2))
