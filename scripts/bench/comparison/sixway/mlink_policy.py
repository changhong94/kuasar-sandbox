from pathlib import Path
import subprocess as sp,json,time
P=Path('/home/hong/deploy/comparison/sixway')
ctl=['nsenter','--net=/run/netns/bench113-m','/home/hong/src/private/kuasar-mlink/test_deps/bin/ttctl','--server','http://127.0.0.1:28080','--data-server','http://127.0.0.1:28081','--admin-server','http://127.0.0.1:28082','--config','/home/hong/data/mlink/client.json','--request-timeout','300']
def inspect(s):return json.loads(sp.check_output(ctl+['--json','template','prewarm','inspect',s],text=True))
def apply(s,p):
 args=['template','prewarm','set',s,'--memory-state',p['memory_state'],'--storage-min-ready',str(p['private_storage_min_ready']),'--storage-ready',str(p['private_storage_target_ready']),'--hot-ready-workers',str(p['hot_ready_workers']),'--wait']
 sp.run(ctl+args,stdout=sp.DEVNULL,check=True)
def prepare(out):
 old=Path('/home/hong/deploy/private-pilot/mlink-template').read_text().strip();new=(P/'mlink-template').read_text().strip();assert old!=new
 record={'old':old,'new':new,'original':{s:inspect(s)['prewarm'] for s in [old,new]}}
 out.write_text(json.dumps(record,indent=2));t=time.monotonic()
 off=dict(memory_state='disabled',private_storage_min_ready=0,private_storage_target_ready=0,hot_ready_workers=0)
 apply(old,off);apply(new,record['original'][old])
 record['preparation_ms']=(time.monotonic()-t)*1000;record['active_new_policy']=inspect(new)['prewarm'];out.write_text(json.dumps(record,indent=2))
 return record
def restore(record):
 # Drop the comparison-only template first, then restore the original template.
 for s in [record['new'],record['old']]:apply(s,record['original'][s])
