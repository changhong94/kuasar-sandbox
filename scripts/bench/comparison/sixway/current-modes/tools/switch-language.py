from pathlib import Path
import sys,json,time,subprocess as sp
B=Path('/home/hong/src/research/report-revision-113');config_path,language,out=sys.argv[1:];cfg=json.loads(Path(config_path).read_text());c=cfg['kuasar-mlink'];ctl=['nsenter','--net=/run/netns/'+c['netns']]+c['ctl'];t=time.monotonic_ns();selected=cfg['_languages'][language]['templates']['kuasar-mlink']
assert not json.loads(sp.check_output(ctl+['list','--json'],text=True))
for l,item in cfg['_languages'].items():
 if l!=language:sp.run(ctl+['template','prewarm','disable',item['templates']['kuasar-mlink'],'--wait'],check=True)
sp.run(ctl+['template','prewarm','set',selected,'--memory-state','full','--storage-min-ready','64','--storage-ready','64','--hot-ready-workers','0','--wait'],check=True)
Path(out).mkdir(parents=True,exist_ok=True);Path(out,'policy-preparation.json').write_text(json.dumps({'language':language,'elapsed_ms':(time.monotonic_ns()-t)/1e6,'template':selected,'storage_ready':64,'vm_pool_capacity':64,'interpreter_executed':False},indent=2))
