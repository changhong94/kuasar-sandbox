from pathlib import Path
import sys,json,subprocess as sp,time
r=Path(sys.argv[1]);assert (r/'complete.json').exists() and (r/'mlink-policy-restored.json').exists()
sys.path.insert(0,'/home/hong/deploy/comparison/sixway');import baseline_config as cfg,runner as b
for p in cfg.PRODUCTS:cfg.require_idle(p)
D=Path('/home/hong/data/kuasar-fork');assert json.loads((D/'adapter-state.json').read_text())=={}
assert [p.name for p in (D/'state').iterdir() if p.is_dir()]==['sixwayseed00001']
assert not list(D.rglob('memory.img'))
sys.path.insert(0,'/home/hong/src/research/sandbox_fork/kuasar-io/kuasar/integrations/e2b');import vm_rpc
v=vm_rpc.execute(D/'state/sixwayseed00001/task.vsock',['/bin/sh','-c','ls /proc/1/fd | wc -l']);assert v['exit_code']==0
time.sleep(2)
b.pr='kuasar-fork';resources=b.resources();seed=json.loads(Path('/home/hong/deploy/kuasar-fork-research/seed-preparation.json').read_text());pid=seed['pid']
seed_fds=len(list(Path('/proc/'+str(pid)+'/fd').iterdir()))
rows=[json.loads(f.read_text()) for f in (r/'timing').glob('[1-5]-kuasar-fork.json')];before=[d['stages']['before']['fds'] for d in rows];settled=[d['stages']['settled']['fds'] for d in rows]
initial_seed=[d['stages']['before']['processes'][str(pid)][2] for d in rows];assert seed_fds==initial_seed[0],(seed_fds,initial_seed)
leases=[]
for p in (D/'ipam').rglob('*'):
 if p.is_file() and p.name.count('.')==3 and all(x.isdigit() for x in p.name.split('.')):leases.append(p.name)
assert len(leases)==1,leases
out={'all_six_idle':True,'fork_adapter_records':0,'fork_remaining_sandboxes':['sixwayseed00001'],'fork_remaining_ipam_leases':leases,'fork_host_resources':resources,'fork_seed_vm_fds':seed_fds,'fork_seed_vm_fds_initial':initial_seed,'fork_guest_agent_fds_at_end':int(v['stdout']),'fork_timing_before_fds':before,'fork_timing_settled_fds':settled,'fork_memory_img_count':0,'mlink_original_prewarm_restored':True,'time':time.time()}
(r/'final-audit.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='fork_host_resources'}))
