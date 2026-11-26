import json,sys,csv,statistics as st
from pathlib import Path
d=Path(sys.argv[1]);rows=[];issues=[]
for f in sorted(d.glob('[1-3]-*.json')):
 a=json.loads(f.read_text());r,diff,pr=f.stem.split('-',2)
 if not a.get('success') or a.get('remaining'):issues.append({'case':f.stem,'error':a.get('error','in progress')});continue
 z=a['stages'];base=z['before'];v={'round':int(r),'content':'different' if diff=='1' else 'same','product':pr,'casesource':f.name}
 for stage in ('live2','paused2','settled'):
  q=z[stage]
  if q.get('supported') is False:
   for metric in ('allocated_mib','pss_delta_mib','extent_mib'):v[stage+'_'+metric]=None
   continue
  v[stage+'_allocated_mib']=(q['allocated_bytes']-base['allocated_bytes'])/2**20;v[stage+'_pss_delta_mib']=q['pss_mib']-base['pss_mib']
  ok=base['extent']['valid'] and q['extent']['valid']
  v[stage+'_extent_mib']=(q['extent']['unique_extent_bytes']-base['extent']['unique_extent_bytes'])/2**20 if ok else None
  if not ok:issues.append({'case':f.stem,'stage':stage,'reason':base['extent'].get('reason') or q['extent'].get('reason')})
 rows.append(v)
def write(name,vals):
 if vals:
  with (d/name).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(vals[0]));w.writeheader();w.writerows(vals)
write('storage_measurements.csv',rows)
cmp=[]
for content in ['same','different']:
 for metric in list(rows[0] if rows else {})[4:]:
  for pr in ['kuasar-off','kuasar-uffd','kuasar-mlink','cube','agentenv','kuasar-fork']:
   v=[x[metric] for x in rows if x['content']==content and x['product']==pr and x[metric] is not None];b=[x[metric] for x in rows if x['content']==content and x['product']=='kuasar-mlink' and x[metric] is not None]
   if v:
    m=st.median(v);cb=st.median(b) if b else None;cmp.append(dict(content=content,metric=metric,product=pr,n=len(v),median=m,min=min(v),max=max(v),mlink=cb,relative_percent=(m/cb-1)*100 if cb and cb>0 else None))
write('storage_comparison.csv',cmp);(d/'storage_audit.json').write_text(json.dumps(dict(complete=(d/'complete.json').exists() and len(rows)==36,valid_workloads=len(rows),issues=issues),indent=2))
