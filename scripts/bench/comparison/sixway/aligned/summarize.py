import json,statistics as st,csv,sys,hashlib
from pathlib import Path
p=Path(sys.argv[1]);rows=[];raw=[];allp=['kuasar-off','kuasar-uffd','kuasar-mlink','cube','agentenv','kuasar-fork']
for f in sorted(p.glob('[1-5]-*.json')):
 d=json.loads(f.read_text());raw.append(d)
 if not d['success'] or d['owned_remaining']:continue
 a=d['stages'];base=a['before'];req=d['pressure']
 row=dict(product=d['product'],round=int(d['round']),ready_ms=d['ready_ms'],short_ms=st.median(d['short_ms']),cpu_guest_wall_ms=d['cpu'][1],cpu_guest_cpu_ms=d['cpu'][2],generate_hash_write_fsync_ms=d['io'][1],pause_ms=d['pause_ms'],resume_ready_ms=d['resume_ms'],preexisting_pss_mib=base['pss_mib'],live_pss_mib=a['live']['pss_mib'],live_delta_pss_mib=a['live']['pss_mib']-base['pss_mib'],memory_workload_observed_max_delta_mib=max(x[1] for x in d['mem_samples'])-base['pss_mib'],after_memory_delta_mib=a['released']['pss_mib']-base['pss_mib'],paused_dir_delta_mib=(a['paused']['allocated_bytes']-base['allocated_bytes'])/1048576 if 'paused' in a else None,written_dir_delta_mib=(a['written']['allocated_bytes']-base['allocated_bytes'])/1048576,live_fd_delta=a['live']['fds']-base['fds'],concurrency2_successes=sum(x.get('success',False) for x in req),concurrency2_attempts=len(req),concurrency2_tasks_per_second=d['throughput'])
 rows.append(row)
def write(n,seq):
 if seq:
  with (p/n).open('w') as g:
   w=csv.DictWriter(g,fieldnames=list(seq[0]));w.writeheader();w.writerows(seq)
write('measurements.csv',rows);pairs=[]
for pr in allp:
 for metric in list(rows[0] if rows else {})[2:]:
  v=[x[metric] for x in rows if x['product']==pr and x[metric] is not None];b=[x[metric] for x in rows if x['product']=='kuasar-mlink']
  if v and b:
   m=st.median(v);cb=st.median(b);pairs.append(dict(product=pr,metric=metric,n=len(v),median=m,min=min(v),max=max(v),mlink_median=cb,relative_percent=(m/cb-1)*100 if cb>0 else ''))
write('comparison.csv',pairs)
complete=len(rows)==30 and (p/'complete.json').exists() and len({(x['product'],x['round']) for x in rows})==30
(p/'audit.json').write_text(json.dumps(dict(full_grid=complete,completed=len(rows),errors=[d['error'] for d in raw if d.get('error')],owned_remaining=[x for d in raw for x in d.get('owned_remaining',[])],pressure_failures=[dict(product=d['product'],round=d['round'],**z) for d in raw for z in d.get('pressure',[]) if not z.get('success')],pressure_attempts=sum(len(d.get('pressure',[])) for d in raw),workload_hashes_verified=[sorted(set(d[k][0] for d in raw if k in d)) for k in ('cpu','io')],runner_sha256=hashlib.sha256((p/'runner.py').read_bytes()).hexdigest()),indent=2))
print('validated batches',len(rows),'full grid',complete)
