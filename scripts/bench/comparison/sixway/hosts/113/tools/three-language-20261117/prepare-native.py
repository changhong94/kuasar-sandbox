from pathlib import Path
import sys,subprocess as s,time,json,os
B=Path('/home/hong/src/research/sixway-languages-20261117');product,language=sys.argv[1:];spec=json.loads((B/'tools/languages.example.json').read_text())['_languages'][language];repo='base' if language=='python' else language
name='languages-'+language+'-2cpu-'+str(time.time_ns());ref='127.0.0.1:5000/e2b/'+repo+'@'+spec['digest'];t=time.monotonic_ns();result={}
if product=='agentenv':
 cmd=['/opt/agentenv-comparison/v0.2.4/aenv','pull',ref,'--name',name,'--cpu','2','--memory','2048','--start-cmd','/bin/sleep infinity','--ready-cmd','/bin/true','--timeout','600']
 s.run(cmd,check=True,env={**os.environ,'XDG_CONFIG_HOME':'/home/hong/deploy/comparison/client'});template=name
else:
 ctl=['/usr/local/bin/cubemastercli','--address','127.0.0.1','--timeout','15m']
 account='getent group 1000 >/dev/null || groupadd -g 1000 user; id user >/dev/null 2>&1 || useradd -o -u 1000 -g 1000 -m -d /home/user -s /bin/bash user; exec /bin/sleep infinity'
 cmd=ctl+['tpl','create-from-image','--image','http://'+ref,'--alias',name,'--writable-layer-size','1G','--expose-port','49983','--probe','49983','--probe-path','/health','--enable-inject-envd','--envd-path','/home/hong/deploy/comparison/assets/cube-envd','--cpu','2000','--memory','2048','--cmd','/bin/sh','--arg=-c','--arg='+account,'--json']
 result=json.loads(s.check_output(cmd,text=True));print(json.dumps(result),flush=True);template=result['job']['template_id']
 result['final']=json.loads(s.check_output(ctl+['tpl','watch','--job-id',result['job']['job_id'],'--interval','500ms','--json'],text=True))
row={'product':product,'language':language,'template':template,'digest':spec['digest'],'source':ref,'elapsed_ms':(time.monotonic_ns()-t)/1e6,'details':result,'guest_start_command':'/bin/sleep infinity','language_training':False}
(B/'results'/('template-'+product+'-'+language+'.json')).write_text(json.dumps(row,indent=2));print(json.dumps(row),flush=True)
