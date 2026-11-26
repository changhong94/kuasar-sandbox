from pathlib import Path
import subprocess as s,time,hashlib,json,os,sys
r=Path(__file__).resolve().parent;d=r/'deployment/fork';e=r/'attempts'/('live-parent-python-'+str(time.time_ns()));e.mkdir()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=dict(section='running-parent',batch='fork-python',attempt=e.name,start=time.time(),source_sha256=digest(d/'live.py'),config_sha256=digest(d/'benchmark-config.json'),runner_sha256=digest(Path(__file__)))
def save(): (e/'status.json').write_text(json.dumps(m,indent=2))
save()
try:
 sys.path.insert(0,str(r/'tools'));from pool_gate import wait
 cfg=json.loads((d/'benchmark-config.json').read_text())['kuasar-fork']
 m['phase']='prepare 64 reserves';save()
 gate=wait(cfg,64,600);(e/'gate.json').write_text(json.dumps(gate));m['phase']='Python live-parent samples';save()
 with (e/'client.log').open('w') as f:s.run(['/home/hong/src/research/python-latest-113/venv/bin/python',d/'live.py','--languages','python','--samples','50','--out',e/'samples'],env={**os.environ,'SIXWAY_OUTER_LOCK':'1'},stdout=f,stderr=s.STDOUT,check=True)
 rows=json.loads((e/'samples/rows.json').read_text());assert len(rows)==50 and all(x['success'] and not x['owned_remaining'] for x in rows)
 m['exit']=0
except BaseException as ex:m.update(exit=1,error=repr(ex));raise
finally:
 m['end']=time.time();save()
 with (e/'vmm.log').open('w') as f:s.run(['journalctl','--since','@'+str(int(m['start'])),'-u','sixway-20261119-fork-vmm','-o','short-precise'],stdout=f)
