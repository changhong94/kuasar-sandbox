import sys,json,subprocess,time,shlex,uuid,importlib.util,requests,base64
from pathlib import Path
M=Path('/opt/bench108');T=M/'tools/language-matched-108';R=M/'results/language-matched-108';name,language=sys.argv[1:];cfg=json.loads((T/(language+'.json')).read_text());spec=importlib.util.spec_from_file_location('bench',T/'bench.py');bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench);c,Sandbox=bench.setup(name,cfg);s=None;out=[]
def call(a):return subprocess.run(c['ctl']+a,text=True,capture_output=True,timeout=90,check=True)
def run(command):
 if Sandbox:
  z=s.commands.run(command,user='root',timeout=60);return z.stdout,z.stderr,z.exit_code
 z=call(['exec',s,'--insecure','--user','root','--','/bin/bash','-l','-c',command]);return z.stdout,z.stderr,z.returncode
try:
 s=Sandbox.create(c['template'],timeout=300) if Sandbox else call(['start',c['template'],'--insecure','--timeout','300']).stdout.strip()
 binary=(T/'exec-probe').read_bytes()
 if Sandbox:s.files.write('/tmp/exec-probe',binary,user='root')
 else:
  z=requests.post('http://127.0.0.1:28081/files',params={'path':'/tmp/exec-probe'},files={'file':('exec-probe',binary)},headers={'E2B-Sandbox-ID':s,'E2B-Sandbox-Port':'49983','Authorization':'Basic '+base64.b64encode(b'root:').decode()},timeout=30);assert z.ok,(z.status_code,z.text)
 assert run('chmod 700 /tmp/exec-probe')[2]==0
 for phase in ['cold','warm']:
  marker='DIAG_'+uuid.uuid4().hex
  command='cd /; '+shlex.join(['exec','/usr/bin/env','-i',*cfg['_env'],'/tmp/exec-probe',cfg['_binary'],cfg['_flag'],cfg['_code'],marker])
  started=time.perf_counter_ns();stdout,stderr,code=run(command);elapsed=(time.perf_counter_ns()-started)/1e6;assert code==0 and stdout.strip()==marker,(stdout,stderr,code)
  guest=json.loads(next(l[6:] for l in stderr.splitlines() if l.startswith('PROBE ')));out.append({'phase':phase,'client_command_complete_ms':elapsed,'guest':guest,'command':command})
 # Shell + transport reference after the two interpreter probes; not a formal sample.
 started=time.perf_counter_ns();stdout,stderr,code=run('printf SHELL_REFERENCE');assert code==0 and stdout=='SHELL_REFERENCE';out.append({'phase':'shell_reference','client_command_complete_ms':(time.perf_counter_ns()-started)/1e6})
finally:
 if s is not None:
  if Sandbox:s.kill()
  else:call(['delete',s])
(R/(language+'-'+name+'-diagnostic.json')).write_text(json.dumps(out,indent=2));print(json.dumps(out),flush=True)
