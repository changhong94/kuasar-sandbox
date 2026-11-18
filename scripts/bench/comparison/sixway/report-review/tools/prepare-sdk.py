import sys,json,os,time,urllib.request,ssl
from pathlib import Path
B=Path('/home/hong/src/research/report-review-113');sys.path.insert(0,str(B/'tools'));import startup
product,language=sys.argv[1:];cfg=json.loads((B/'tools/config.json').read_text());c,_=startup.setup(product,cfg)
from e2b import Template,wait_for_timeout
spec=json.loads((B/'tools/languages.example.json').read_text())['_languages'][language];repository='base' if language=='python' else language
ref='169.254.169.254:5000/e2b/'+repository+'@'+spec['digest'];name='languages-'+language+'-'+product+'-'+str(time.time_ns())
def log(e):print(e.message.rstrip(),file=sys.stderr,flush=True)
# Same guest account setup for every language, including images with UID 1000 already used.
account='getent group 1000 >/dev/null || groupadd -g 1000 user; id user >/dev/null 2>&1 || useradd -o -u 1000 -g 1000 -m -d /home/user -s /bin/bash user'
template=(Template().from_image(ref).set_user('root').run_cmd(account).set_workdir('/').set_start_cmd('/bin/sleep infinity',wait_for_timeout(2000)))
start=time.monotonic_ns();info=Template.build(template,name=name,cpu_count=2,memory_mb=2048,on_build_logs=log)
req=urllib.request.Request(c['api_url']+'/templates/'+info.template_id+'/builds/'+info.build_id+'/status',headers={'X-API-Key':Path(c['key_file']).read_text().strip()})
context=ssl.create_default_context(cafile=c['ca_file']);status=json.load(urllib.request.urlopen(req,context=context,timeout=30));assert status['status']=='ready' and status['kind']=='snp',status
row={'product':product,'language':language,'template':status['templateID'],'digest':spec['digest'],'source':ref,'elapsed_ms':(time.monotonic_ns()-start)/1e6,'build_id':info.build_id,'status':status,'guest_start_command':'/bin/sleep infinity','language_training':False}
(B/'results'/('template-'+product+'-'+language+'.json')).write_text(json.dumps(row,indent=2));print(json.dumps(row))
