from pathlib import Path
import shutil,json
H=Path('/home/hong');old=H/'results/fiveway-matched-20261113_075338';D=H/'deploy/comparison/sixway';D.mkdir(parents=True,exist_ok=True)
for name in ['runner.py','retained.py','extent_accounting.py','summarize.py','storage-summary.py']:shutil.copy2(old/'tools'/name,D/name)
p=D/'runner.py';s=p.read_text();s=s.replace("template=(P/'mlink-template')","template=(D/'sixway/mlink-template')");s=s.replace("'kuasar-uffd','kuasar-mlink']","'kuasar-uffd','kuasar-mlink','kuasar-fork']",1).replace("'bench113-u','bench113-m']))","'bench113-u','bench113-m','bench113-fork']))",1)
s=s.replace(" if pr.startswith('kuasar'):"," if pr=='kuasar-fork':\n  c=dict(api_key=Path('/home/hong/deploy/kuasar-fork-research/api-key').read_text().strip(),api_url='http://127.0.0.1:18884',template_id='base');kw={}\n elif pr.startswith('kuasar'):",1)
s=s.replace("if pr in ('agentenv','cube'):","if pr in ('agentenv','cube','kuasar-fork'):",1).replace("if pr=='agentenv':os.environ['E2B_SANDBOX_URL']","if pr in ('agentenv','kuasar-fork'):os.environ['E2B_SANDBOX_URL']",1)
s=s.replace("'kuasar-mlink':'bench-private-mlink'","'kuasar-mlink':'bench-private-mlink','kuasar-fork':'bench-kuasar-fork'")
s=s.replace("'kuasar-mlink':['mlink3']","'kuasar-mlink':['mlink3'],'kuasar-fork':['kuasar-fork']")
a=s.index("  record('released');t=clock();pause(s)");z=s.index("  assert cmd(s,'sha256sum",a)
s=s[:a]+'''  record('released')
  if pr=='kuasar-fork':
   out.update(pause_ms=None,resume_ms=None,unsupported=['persistent_pause_resume'],filesystem_write_backing='guest RAM overlay')
  else:
   t=clock();pause(s);out['pause_ms']=(clock()-t)*1000;record('paused')
   t=clock();s=resume(s);ready(s,'printf READY','READY');out['resume_ms']=(clock()-t)*1000
'''+s[z:]
s=s.replace("{'runs':25}","{'runs':30}");compile(s,str(p),'exec');p.write_text(s)
p=D/'retained.py';s=p.read_text().replace("'kuasar-mlink':['mlink3']","'kuasar-mlink':['mlink3'],'kuasar-fork':['kuasar-fork']")
s=s.replace("  for s in owned.values():b.pause(s)\n  time.sleep(1);snap('paused2')",'''  if pr=='kuasar-fork':
   out['unsupported']=['persistent_pause_resume'];out['filesystem_write_backing']='guest RAM overlay'
   out['stages']['paused2']={'supported':False,'reason':'persistent pause would require an unsupported memory snapshot'}
  else:
   for s in owned.values():b.pause(s)
   time.sleep(1);snap('paused2')''')
s=s.replace('   s=b.resume(s);owned[key]=s;',"   if pr!='kuasar-fork':s=b.resume(s)\n   owned[key]=s;").replace("{'runs':30}","{'runs':36}");compile(s,str(p),'exec');p.write_text(s)
p=D/'summarize.py';s=p.read_text().replace("'cube','agentenv']","'cube','agentenv','kuasar-fork']").replace("(a['paused']['allocated_bytes']-base['allocated_bytes'])/1048576","(a['paused']['allocated_bytes']-base['allocated_bytes'])/1048576 if 'paused' in a else None").replace("if x['product']==pr]","if x['product']==pr and x[metric] is not None]").replace('len(rows)==25','len(rows)==30').replace("for x in rows})==25","for x in rows})==30");compile(s,str(p),'exec');p.write_text(s)
p=D/'storage-summary.py';s=p.read_text().replace("'cube','agentenv']","'cube','agentenv','kuasar-fork']").replace("  q=z[stage];v[stage+'_allocated_mib']",'''  q=z[stage]
  if q.get('supported') is False:
   for metric in ('allocated_mib','pss_delta_mib','extent_mib'):v[stage+'_'+metric]=None
   continue
  v[stage+'_allocated_mib']''').replace('len(rows)==30','len(rows)==36');compile(s,str(p),'exec');p.write_text(s)
for name in ['growth','arrays']:
 (D/name).mkdir(exist_ok=True);s=(old/name/'run.py').read_text().replace(str(old/'tools'),str(D));(D/name/'run.py').write_text(s)
shutil.copy2(H/'src/changhong94/kuasar-sandbox/scripts/bench/comparison/fiveway/write_sandbox_configs.py',D/'baseline_config.py')
for name in ['preflight.py','mlink_policy.py']:shutil.copy2(Path(__file__).resolve().parent/name,D/name)
print('six-way workloads generated from frozen five-way sources')
