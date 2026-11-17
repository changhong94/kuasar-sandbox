import sys,os,json,time,subprocess,shlex,uuid,importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('bench','/opt/bench108/tools/python-print-108/bench.py');bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)
name=sys.argv[1];cfg=json.loads(Path('/opt/bench108/tools/python-print-108/config.json').read_text());c,Sandbox=bench.setup(name,cfg);s=None;rows=[]
def call(args):return subprocess.run(args,text=True,capture_output=True,timeout=90,check=True)
try:
 s=Sandbox.create(c['template'],timeout=180) if c['kind']=='e2b' else call(c['ctl']+['start',c['template'],'--insecure','--timeout','180']).stdout.strip()
 for phase in ['cold','warm']:
  marker='PROFILE_'+uuid.uuid4().hex;cmd=shlex.join(['exec','/usr/local/bin/python3','-X','importtime','-c','import sys; print(sys.argv[1], flush=True)',marker]);t=time.perf_counter_ns()
  if c['kind']=='e2b':
   z=s.commands.run(cmd,user='root',timeout=60);stdout,stderr,code=z.stdout,z.stderr,z.exit_code
  else:
   z=call(c['ctl']+['exec',s,'--insecure','--','/bin/sh','-c',cmd]);stdout,stderr,code=z.stdout,z.stderr,z.returncode
  elapsed=(time.perf_counter_ns()-t)/1e6;assert code==0 and stdout.strip()==marker
  rows.append(dict(phase=phase,elapsed_ms=elapsed,imports=stderr))
finally:
 if s is not None:
  if c['kind']=='e2b':s.kill()
  else:call(c['ctl']+['delete',s])
Path('/opt/bench108/results/python-opt-108/'+name+'-imports.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
