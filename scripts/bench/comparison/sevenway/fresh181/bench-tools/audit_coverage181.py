"""Coverage only. Never declares the overall task complete or stops monitoring."""
from pathlib import Path
import json,time
R=Path('/home/hong/codex-work/sevenway-fresh-181');M=R/'measurements';cfg=json.load(open(R/'tools/config.json'));products=[p for p in cfg if not p.startswith('_')];rows=[]
def check(label,files,expected,predicate):
 good=[];bad=[]
 for f in files:
  try:
   d=json.load(open(f));(good if predicate(d) else bad).append(str(f.relative_to(R)))
  except Exception as e:bad.append({'file':str(f),'error':repr(e)})
 rows.append(dict(case=label,expected=expected,valid=len(good),complete=len(good)==expected and not bad,invalid=bad))
for p in products:
 for lang in ['python','node','ruby']:
  check('startup/'+p+'/'+lang,(M/'startup'/lang/p).glob('[0-9][0-9].json'),51,lambda d:d.get('success') and d.get('destroyed'))
 for stage in ['resources','lifecycle']:
  check(stage+'/'+p,(M/stage/p).glob('[0-9][0-9].json'),51,lambda d:d.get('success') and not d.get('owned_remaining'))
 pause=M/'pause-restore'/(p+'.json')
 if pause.exists():
  samples=json.load(open(pause)).get('samples',[]);valid={d['iteration']for d in samples if d.get('success')and d.get('delete_ack')}
 else: valid=set()
 rows.append(dict(case='pause-restore/'+p,expected=51,valid=len(valid),complete=valid==set(range(51))))
 check('storage/'+p,(M/'storage'/p).glob('*.json'),6,lambda d:d.get('success') and not d.get('owned_remaining'))
 check('memory/'+p,[M/'memory'/(p+'.json')]if (M/'memory'/(p+'.json')).exists()else[],1,lambda d:d.get('success') and not d.get('owned') and len(d.get('arrays',{}))==3)
 for gap in [0,10,25,50,100]:
  f=M/'burst'/p/str(gap)/'result.json'
  check('burst/'+p+'/'+str(gap),[f]if f.exists()else[],1,lambda d:d.get('measurement_complete') and not d.get('owned_remaining'))
result=dict(checked_unix=time.time(),coverage=rows,incomplete=[r['case']for r in rows if not r['complete']],additional_required=['snapshot mode source/caching audit','pool preparation event count audit','live parent pause trace audit','all failed request server-cause attribution','CN/EN PDF','owned service cleanup'],task_complete=False)
f=R/'coverage-audit.json';q=f.with_suffix('.tmp');q.write_text(json.dumps(result,indent=2));q.replace(f);print('CORE_CASES',len(rows),'INCOMPLETE',len(result['incomplete']))
