from pathlib import Path
import json,statistics
M=Path('/opt/bench108/results/fork-opt2-108')
def med(v):return statistics.median(v)
out={}
for variant,log in [('baseline','baseline-server.log'),('after','after-server.log')]:
 rows=[json.loads(p.read_text()) for p in sorted((M/variant).glob('[0-9]*-kuasar-fork.json'))];assert len(rows)==10
 events=[]
 for line in (M/log).read_text().splitlines():
  if line.startswith('E2B_TIMING '):events.append(json.loads(line[len('E2B_TIMING '):]))
 stages={};per=[]
 for row in rows:
  sid=row['sandbox_id'];ev=[e for e in events if e.get('sid')==sid];d={e['stage']:e for e in ev}
  z={'sid':sid,'total':row['ready_ms'],'create_api':row['api_ms'],'first_command_client':row['ready_ms']-row['api_ms']}
  for name in ['pool_lock_wait','pool_assignment_save','pool_lease','image_intent','image_disk_attach','image_mount','image_publish','image_bind_total','execute_rpc','execute_total']:
   if name in d:z[name]=d[name]['elapsed_ms']
  z['admin_get']=next(e['elapsed_ms'] for e in ev if e['stage']=='admin' and e.get('action')=='sandbox-get')
  z['client_create_overhead']=z['create_api']-z['image_bind_total']
  z['first_command_outside_rpc']=z['first_command_client']-z['execute_rpc']
  z['mount_guest']=d['image_mount']['guest']['total_us']/1000
  z['mount_handshake']=d['image_mount']['guest']['host_handshake_us']/1000
  z['exec_guest']=d['execute_rpc']['guest']['total_us']/1000
  z['exec_handshake']=d['execute_rpc']['guest']['host_handshake_us']/1000
  # Durability commit intervals contained within this request's own save stage.
  committed=[]
  for name in ['pool_assignment_save','image_intent','image_publish']:
   if name not in d:continue
   v=d[name];ds=[e for e in events if e['stage']=='durable_save' and v['started_ns']<=e['started_ns'] and e['ended_ns']<=v['ended_ns']]
   # Intent can include another request's commit while waiting on the lock:
   # do not attribute that commit to this request; report enclosing stage instead.
   if name!='image_intent' and ds:committed.append(ds[-1]['commit_ms'])
  z['assignment_and_publish_commit']=sum(committed)
  per.append(z)
  for k,v in z.items():
   if k!='sid':stages.setdefault(k,[]).append(v)
 out[variant]={'median_ms':{k:med(v) for k,v in stages.items()},'requests':per,'end_to_end':json.loads((M/variant/'summary.json').read_text())}
(M/'stages.json').write_text(json.dumps(out,indent=2))
for v,d in out.items():print(v,json.dumps(d['median_ms'],indent=2))
