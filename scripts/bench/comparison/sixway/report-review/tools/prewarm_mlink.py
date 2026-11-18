from pathlib import Path
import json,subprocess as sp,time
B=Path('/home/hong/src/research/sixway-aligned-20261117');c=json.loads(Path('/home/hong/src/research/sixway-formal-python-113/tools/config.json').read_text())['kuasar-mlink'];ctl=['nsenter','--net=/run/netns/'+c['netns']]+c['ctl'];ctl[-1]='300';sid=json.loads((B/'results/mlink-template.json').read_text())['template']
raw=sp.check_output(['nsenter','--net=/run/netns/'+c['netns'],'curl','-fsS','http://127.0.0.1:29082/internal/status'],text=True);(B/'results/mlink-prewarm-before.json').write_text(raw)
t=time.monotonic()
for tpl in json.loads(raw)['templates']:
 if tpl['id']!=sid and tpl['prewarm']['memory_state']!='disabled':sp.run(ctl+['template','prewarm','set',tpl['id'],'--memory-state','disabled','--storage-min-ready','0','--storage-ready','0','--hot-ready-workers','0','--wait'],check=True)
sp.run(ctl+['template','prewarm','set',sid,'--memory-state','full','--storage-min-ready','2','--storage-ready','2','--hot-ready-workers','0','--wait'],check=True)
(B/'results/mlink-prewarm.json').write_text(json.dumps(dict(template=sid,elapsed_ms=(time.monotonic()-t)*1000),indent=2))
