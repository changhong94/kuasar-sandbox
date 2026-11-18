"""Two independent sandboxes; destroy each order and execute in the survivor."""
import sys,json,subprocess as sp,uuid,shlex
from pathlib import Path
B=Path('/home/hong/src/research/report-review-113');sys.path.insert(0,str(B/'tools'))
from languages import select_language,print_command
from pool_gate import wait
from startup import setup
product,language=sys.argv[1:];config=select_language(json.loads((B/'tools/config.json').read_text()),language);c,Sandbox=setup(product,config);out={}
def create():
 return Sandbox.create(c['template'],timeout=300,**c.get('create_kwargs',{})) if Sandbox else sp.check_output(c['ctl']+['start',c['template'],'--insecure','--timeout','300'],text=True).strip()
def sid(s):return s.sandbox_id if Sandbox else s
def execute(s,command):
 if Sandbox:
  result=s.commands.run(command,user='root',timeout=60);assert result.exit_code==0,result;return result.stdout
 return sp.check_output(c['ctl']+['exec',s,'--insecure','--user','root','--','/bin/bash','-l','-c',command],text=True,timeout=90)
def destroy(s):
 if Sandbox:s.kill()
 else:sp.run(c['ctl']+['delete',s],check=True,stdout=sp.DEVNULL,timeout=90)
for victim in [0,1]:
 wait(c);owned=[];row={}
 try:
  owned=[create()];owned.append(create());assert sid(owned[0])!=sid(owned[1]);row['ids']=[sid(x) for x in owned]
  values=[uuid.uuid4().hex,uuid.uuid4().hex];path='/tmp/sixway-independent-'+uuid.uuid4().hex
  for i,s in enumerate(owned):execute(s,'printf %s '+shlex.quote(values[i])+' > '+shlex.quote(path))
  for i,s in enumerate(owned):assert execute(s,'cat '+shlex.quote(path))==values[i]
  destroy(owned[victim]);owned[victim]=None;survivor=owned[1-victim]
  marker='READY_'+uuid.uuid4().hex;native='NATIVE_'+uuid.uuid4().hex;command,_=print_command(language,marker,native)
  assert execute(survivor,command)==native+'\n'+marker+'\n'
  assert execute(survivor,'cat '+shlex.quote(path))==values[1-victim]
  row.update(success=True,survivor_print=marker,isolated_files=True)
 finally:
  for s in owned:
   if s is not None:destroy(s)
  wait(c)
 out[str(victim)]=row
(B/'results'/('independent-'+product+'-'+language+'.json')).write_text(json.dumps(out,indent=2));print(product,language,'both destruction orders passed',flush=True)
