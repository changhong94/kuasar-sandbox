from pathlib import Path
import shutil,json,subprocess,os
old=Path('/home/hong/src/research/sevenway-fresh-20261124');new=Path('/home/hong/src/research/sevenway-current-20261126')
assert not new.exists();new.mkdir()
for section in ['fork2','six']:
 target=new/section;target.mkdir()
 for sub in ['results','logs','preparation','private']:(target/sub).mkdir(mode=0o700 if sub=='private' else 0o755)
# Only source and deployment inputs, never measurement rows or completion flags.
for section in ['fork2/tools','six/tools']:
 shutil.copytree(old/section,new/section,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for p in (old/'six').glob('*.py'):shutil.copy2(p,new/'six'/p.name)
shutil.copy2(old/'six_driver.py',new/'six_driver.py')
for p in new.rglob('*.py'):
 s=p.read_text().replace(str(old),str(new));p.write_text(s)
for p in (new/'six/tools').glob('*.json'):
 s=p.read_text().replace(str(old),str(new));p.write_text(s);p.chmod(0o600)
# Dedicated new private keys are refreshed by the six-product deployment stage.
p=new/'fork2/tools/full_run.py';s=p.read_text().replace("'pool50.py'),'current','50'","'pool50.py'),'current','20'");p.write_text(s)
p=new/'fork2/tools/pool50.py';s=p.read_text().replace(" empty();run('systemctl'", " existing=out/f'{i:02d}.json'\n if existing.exists():\n  row=json.loads(existing.read_text());assert row['success'];continue\n empty();run('systemctl'",1);p.write_text(s)
p=new/'fork2/tools/startup_all.py';s=p.read_text().replace("  p.stdin.write(json.dumps([lang,i])", "  existing=R/'results/startup'/f'{lang}-fork2-{i:02d}.json'\n  if existing.exists():\n   row=json.loads(existing.read_text());assert row['success'] and row['destroyed'] and not row.get('pool_error');continue\n  p.stdin.write(json.dumps([lang,i])");p.write_text(s)
# Child progress must never replace the driver's completed-stage ledger.
p=new/'fork2/tools/resume_remote.py';s=p.read_text().replace("R/'status.json'","R/'remote-status.json'");p.write_text(s)
# Retain partial successful pause/restore samples on repair/restart.
p=new/'fork2/tools/pause_restore.py';s=p.read_text().replace('rows=[]\nfor i in range(a.count+1):',"rows=json.loads(pathlib.Path(a.output).read_text())['samples'] if pathlib.Path(a.output).exists() else []\nfor i in range(a.count+1):\n if any(r.get('iteration')==i and r.get('success') and r.get('delete_ack') for r in rows):continue\n if any(r.get('iteration')==i for r in rows):raise RuntimeError('Review failed sample and cleanup before resuming')") ;p.write_text(s)
# The cleanup check should ignore the benchmark driver, not a historic unit name.
p=new/'fork2/tools/cleanup.py';s=p.read_text().replace("'fork2-full-current' not in l", "'sevenway-current' not in l");p.write_text(s)
(new/'scope.json').write_text(json.dumps({'products':7,'fresh_results':True,'startup_samples':50,'startup_warmup':1,'whole_pool_rounds':20,'slots':64,'prepare_refill_concurrency':8,'languages':['python','node','ruby'],'nonstartup_language':'python','burst_requests':256,'gaps_ms':[0,10,25,50,100],'successful_burst_instances':'retain until group end','source':'latest committed Fork2; six existing product baselines','template_policy':'retain proven113 image catalogs and generic prefetch policy, disclose per-product preparation separately'},indent=2))
print(new)
