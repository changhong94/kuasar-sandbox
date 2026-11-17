from pathlib import Path
import json,statistics
R=Path('/opt/bench108/results/fork-opt3-108');out={}
for variant in ['baseline','round1','round2','round3','round4','round5','loop-followup']:
 if not (R/variant/'summary.json').exists():continue
 rows=[json.loads(p.read_text()) for p in (R/variant).glob('[0-9]*-kuasar-fork.json')]
 events=[json.loads(l[11:]) for l in (R/(variant+'-server.log')).read_text().splitlines() if l.startswith('E2B_TIMING ')]
 per=[]
 for row in rows:
  sid=row['sandbox_id'];ev=[e for e in events if e.get('sid')==sid];d={e['stage']:e for e in ev}
  z={'sid':sid,'total':row['ready_ms'],'create_api':row['api_ms'],'first_command_client':row['ready_ms']-row['api_ms']}
  for n in ['pool_assignment_save','pool_lease','image_disk_attach','image_mount','image_publish','image_bind_total','execute_rpc']:
   z[n]=d[n]['elapsed_ms']
  z['mount_guest']=d['image_mount']['guest']['total_us']/1000;z['exec_guest']=d['execute_rpc']['guest']['total_us']/1000
  h=json.loads(d['image_mount']['helper'])
  for k,v in h.items():
   if isinstance(v,(float,int)):z[k]=v/1000
  per.append(z)
 med={k:statistics.median(x[k] for x in per) for k in per[0] if k!='sid'}
 mr=[json.loads(p.read_text()) for p in (R/variant).glob('[0-9]*-kuasar-mlink.json')];names={'thinkactor-'+x['sandbox_id'] for x in mr}
 ml=[]
 for l in (R/(variant+'-mlink.log')).read_text().splitlines():
  try:e=json.loads(l)['fields']
  except (ValueError,KeyError):continue
  if e.get('event')=='pico_restore' and e.get('thinkactor_name') in names:ml.append(e)
 assert len(ml)==10,len(ml)
 mm={k:statistics.median(e[k] for e in ml)/1000 for k in ['checkpoint_validate_us','device_acquire_us','vmm_restore_us','guest_ready_us','publish_us','total_us']}
 out[variant]={'end_to_end':json.loads((R/variant/'summary.json').read_text()),'fork_median_ms':med,'fork_requests':per,'mlink_restore_ms':mm}
 print(variant,json.dumps({'end_to_end':out[variant]['end_to_end'],'fork_ms':med,'mlink_restore_ms':mm},ensure_ascii=False))
(R/'stages.json').write_text(json.dumps(out,indent=2))
