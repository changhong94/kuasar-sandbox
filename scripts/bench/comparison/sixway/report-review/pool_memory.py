"""PSS partition at 64 idle ready slots; does not claim empty-pool marginal cost."""
from pathlib import Path
import argparse,fcntl,json,statistics,subprocess,sys,time
B=Path('/home/hong/src/research/report-review-113');sys.path.insert(0,str(B/'tools'))
import runner as b
from pool_gate import wait

def worker(product):
 b.pr=product;b.setup(product);gate=wait(b.c,capacity=64,timeout=600)
 measurements=[]
 for _ in range(5):
  resources=b.resources();processes=resources['processes']
  if product=='kuasar-fork':
   state=json.loads(Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json').read_text())
   records=[r for r in state.values() if r.get('pool_state')=='ready']
   assert len(records)==64,len(records)
   vms=[str(r['pid']) for r in records];holders=[str(r['holder_pid']) for r in records]
   slot_ids=set(vms+holders)
  else:
   vms=[pid for pid,r in processes.items() if r[0]=='cloud-hyperviso']
   assert len(vms)==64,len(vms)
   slot_ids=set(vms)
  assert slot_ids<=set(processes),(product,slot_ids-set(processes))
  values=[processes[p][1]/1024 for p in vms]
  pool_pss=sum(processes[p][1]/1024 for p in slot_ids)
  measurements.append({'total_product_pss_mib':resources['pss_mib'],'slot_processes_pss_mib':pool_pss,'common_processes_pss_mib':resources['pss_mib']-pool_pss,'slot_processes_average_pss_mib':pool_pss/64,'vm_process_median_pss_mib':statistics.median(values),'vm_process_min_pss_mib':min(values),'vm_process_max_pss_mib':max(values),'slot_process_ids':sorted(slot_ids),'processes':processes})
  time.sleep(1)
 wait(b.c,capacity=64,timeout=600)
 summary={k:statistics.median(m[k] for m in measurements) for k in measurements[0] if k not in ('slot_process_ids','processes')}
 return {'product':product,'capacity':64,'ready_gate':gate,'samples':measurements,'summary':summary,'definition':'PSS partition while 64 slots are idle and ready; slot VMMs plus per-slot namespace-holder processes where present. Common includes seed VM, controllers and dedicated cache/store processes. This is attribution at 64 slots, not a before/after empty-pool experiment; excludes most kernel memory and unmapped page cache.'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--worker');args=p.parse_args()
 if args.worker:print(json.dumps(worker(args.worker)))
 else:
  with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   results={}
   for product in ('kuasar-fork','kuasar-mlink'):
    results[product]=json.loads(subprocess.check_output(['nsenter','--net=/run/netns/'+b.ns[product],sys.executable,__file__,'--worker',product],text=True))
   (B/'results/pool-memory.json').write_text(json.dumps(results,indent=2))
