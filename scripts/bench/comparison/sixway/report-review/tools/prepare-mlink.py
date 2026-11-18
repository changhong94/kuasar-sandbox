from pathlib import Path
import subprocess as s,json,time,shutil
B=Path('/home/hong/src/research/report-review-113');cfg=json.loads((B/'tools/config.json').read_text())['kuasar-mlink'];ctl=cfg['ctl'];ctl[-1]='600'
assert not json.loads(s.check_output(ctl+['list','--json'],text=True))
s.run(ctl+['template','prewarm','disable',cfg['template'],'--wait'],check=True)
for name,old,new in [('mlink-env.sh','POOL_CAPACITY=64','POOL_CAPACITY=2'),('start.sh','write_node_configs 64 1000 2 2 64','write_node_configs 2 1000 2 2 2')]:
 p=Path('/home/hong/deploy/mlink-generic')/name;shutil.copyfile(p,B/'backups'/(name+'.before-successful-restart'));text=p.read_text();assert old in text;text=text.replace(old,new);p.write_text(text)
t=time.monotonic_ns();s.run(['systemctl','restart','bench-mlink-generic'],check=True)
for _ in range(600):
 p=s.run(ctl+['list','--json'],capture_output=True,text=True)
 if p.returncode==0:break
 time.sleep(.1)
else:raise RuntimeError('mlink restart failed')
(B/'results/mlink-restart.json').write_text(json.dumps({'elapsed_ms':(time.monotonic_ns()-t)/1e6,'pool_capacity':2},indent=2))
spec=json.loads((B/'tools/languages.example.json').read_text())['_languages']
for lang in ['python','node','ruby']:
 disk='/home/hong/src/research/sandbox_fork/tools/generic-pool-10/base-common.erofs' if lang=='python' else str(B/'assets'/lang/'root.ext4')
 t=time.monotonic_ns();sid=s.check_output(ctl+['template','import',disk,'--name','languages-'+lang+'-2cpu-'+str(time.time_ns()),'--cpu-count','2','--memory-mb','2048','--disk-size-mb','1024','--scope','full'],text=True).strip()
 row={'product':'kuasar-mlink','language':lang,'template':sid,'digest':spec[lang]['digest'],'disk':disk,'elapsed_ms':(time.monotonic_ns()-t)/1e6,'language_training':False};(B/'results'/('template-kuasar-mlink-'+lang+'.json')).write_text(json.dumps(row,indent=2));print(json.dumps(row),flush=True)
 t=time.monotonic_ns();s.run(ctl+['template','prewarm','set',sid,'--memory-state','full','--storage-min-ready','2','--storage-ready','2','--hot-ready-workers','0','--wait'],check=True)
 row['prewarm_ms']=(time.monotonic_ns()-t)/1e6;(B/'results'/('template-kuasar-mlink-'+lang+'.json')).write_text(json.dumps(row,indent=2));print(lang,'prewarm',row['prewarm_ms'],flush=True)
