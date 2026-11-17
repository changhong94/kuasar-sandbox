from pathlib import Path
import subprocess as s,json,time
B=Path('/home/hong/src/research/sixway-languages-20261117');cfg=json.loads((B/'tools/config.json').read_text())['kuasar-mlink'];ctl=cfg['ctl'];ctl[-1]='600';spec=json.loads((B/'tools/languages.example.json').read_text())['_languages']
assert not json.loads(s.check_output(ctl+['list','--json'],text=True))
previous=json.loads((B/'results/template-kuasar-mlink-python.json').read_text())['template'];s.run(ctl+['template','prewarm','disable',previous,'--wait'],check=True)
for lang in ['node','ruby']:
 path=B/'results'/('template-kuasar-mlink-'+lang+'.json')
 if path.exists():row=json.loads(path.read_text());sid=row['template']
 else:
  disk=str(B/'assets'/lang/'root.ext4');t=time.monotonic_ns();sid=s.check_output(ctl+['template','import',disk,'--name','languages-'+lang+'-2cpu-'+str(time.time_ns()),'--cpu-count','2','--memory-mb','2048','--disk-size-mb','1024','--scope','full'],text=True).strip();row={'product':'kuasar-mlink','language':lang,'template':sid,'digest':spec[lang]['digest'],'disk':disk,'elapsed_ms':(time.monotonic_ns()-t)/1e6,'language_training':False}
 t=time.monotonic_ns();s.run(ctl+['template','prewarm','set',sid,'--memory-state','full','--storage-min-ready','2','--storage-ready','2','--hot-ready-workers','0','--wait'],check=True);row['prewarm_ms']=(time.monotonic_ns()-t)/1e6;path.write_text(json.dumps(row,indent=2));print(json.dumps(row),flush=True)
 s.run(ctl+['template','prewarm','disable',sid,'--wait'],check=True)
