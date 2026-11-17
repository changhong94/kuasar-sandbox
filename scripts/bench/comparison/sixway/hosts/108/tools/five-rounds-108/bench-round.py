from pathlib import Path
import subprocess as sp,sys,datetime,json
M=Path('/opt/bench108');n=sys.argv[1];T=M/'tools/five-rounds-108'/('round'+n);R=M/'results/five-rounds-108'/('round'+n);py=str(M/'venv/bin/python');ns=['nsenter','--net=/run/netns/b108-fork',py]
started=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
sp.run(ns+[str(T/'fork-pristine.py')],check=True)
with (R/'pre-bench-ready.json').open('w') as f:sp.run(ns+[str(M/'tools/fork-opt3-108/wait-ready.py')],stdout=f,check=True)
sp.run(['python3',str(M/'tools/snapshot-pool-108/resources.py'),str(R/'pre-bench-resources.json')],check=True)
cg=sp.check_output(['systemctl','show','bench108-fork','-p','ControlGroup','--value'],text=True).strip();cpu=Path('/sys/fs/cgroup'+cg+'/cpu.stat');(R/'pre-bench-cpu.txt').write_text(cpu.read_text())
with (R/'bench-summary.log').open('w') as f:sp.run([py,str(T/'run-bench.py')],stdout=f,stderr=sp.STDOUT,check=True)
(R/'post-bench-cpu.txt').write_text(cpu.read_text())
with (R/'fork-timing.log').open('w') as f:sp.run(['journalctl','-u','bench108-fork','--since',started,'--no-pager','-o','cat'],stdout=f,check=True)
with (R/'analysis.log').open('w') as f:sp.run([py,str(T/'analyze.py')],stdout=f,stderr=sp.STDOUT,check=True)
with (R/'restore-phases.log').open('w') as f:sp.run([py,str(T/'restore-phases.py')],stdout=f,stderr=sp.STDOUT,check=True)
d=json.loads((R/'stages.json').read_text());print(json.dumps({l:{p:{k:v[k] for k in ['ready_ms','max_ms','api_ms','exec_to_print_ms']} for p,v in a.items()} for l,a in d.items()}),flush=True)
for name in ['validate','tcp-validate','network-validate','languages-survivors','validate-certificate','validate-gate','validate-staging']:
 with (R/(name+'.log')).open('w') as f:sp.run(ns+[str(T/(name+'.py'))],stdout=f,stderr=sp.STDOUT,check=True)
with (R/'final-ready.json').open('w') as f:sp.run(ns+[str(M/'tools/fork-opt3-108/wait-ready.py')],stdout=f,check=True)
sp.run(['python3',str(M/'tools/snapshot-pool-108/resources.py'),str(R/'final-resources.json')],check=True)
print('validation complete',n,flush=True)
