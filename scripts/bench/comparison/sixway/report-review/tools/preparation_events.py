from pathlib import Path
import json,subprocess as sp
B=Path('/home/hong/src/research/sixway-aligned-20261117');base=json.loads((B/'results/deployment-preparation.json').read_text());out={}
for unit,product in [('kuasar-comparison-node','kuasar-off'),('bench-private-uffd-serve','kuasar-uffd')]:
 row=next(x for x in base if x['name']=='restart-'+unit);start=row['started_unix_ns'];raw=sp.check_output(['journalctl','-u',unit,'--since','@'+str(start//10**9),'-o','json','--no-pager'],text=True)
 events=[]
 for line in raw.splitlines():
  d=json.loads(line);msg=d.get('MESSAGE','')
  if any(s in msg for s in ['NODE_READY','COMPARISON_READY','template:','snapshot template built','Build finished','Started ','Stopping ']):events.append(dict(time_unix_us=int(d['__REALTIME_TIMESTAMP']),message=msg))
 ready=next((e for e in events if 'NODE_READY' in e['message'] or 'COMPARISON_READY' in e['message']),None)
 out[product]=dict(events=events,restart_request_to_template_ready_ms=(ready['time_unix_us']*1000-start)/1e6 if ready else None,definition='includes stopping old dedicated service and building new native-sleep template; cached image artifacts retained')
(B/'results/preparation-events.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v['restart_request_to_template_ready_ms'] for k,v in out.items()}))
