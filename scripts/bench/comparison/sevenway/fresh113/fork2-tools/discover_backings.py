import pathlib,json,time,subprocess,os
from e2b import Sandbox
R=pathlib.Path('/home/hong/src/research/sevenway-current-20261126/fork2');c=json.load(open('/srv/fork2/console.json'));opts=dict(api_key=c['key'],api_url=c['api'],sandbox_url='http://127.0.0.1:19211');out={};preps={}
for lang in ['python','node','ruby']:
 t=time.monotonic();s=Sandbox.create(json.load(open('/srv/fork2/data/registry/'+lang+'.json'))['template_id'],timeout=300,**opts)
 try:
  assert s.commands.run('true',user='root',cwd='/',timeout=60).exit_code==0
  paths=set()
  for p in pathlib.Path('/proc').glob('[0-9]*'):
   try:
    if 'fork2-'not in (p/'cgroup').read_text():continue
    for line in (p/'maps').read_text().splitlines():
     if '/srv/fork2/data/template-memory-cache-v2/'in line:paths.add(line.split()[-1])
   except (FileNotFoundError,PermissionError):pass
  assert len(paths)==1,paths;out[lang]=next(iter(paths));preps[lang]={'ms':(time.monotonic()-t)*1000,'interpreter_started':False}
 finally:s.kill()
(R/'results/template-backings.json').write_text(json.dumps(out,indent=2));(R/'results/backing-discovery-cost.json').write_text(json.dumps(preps,indent=2))
