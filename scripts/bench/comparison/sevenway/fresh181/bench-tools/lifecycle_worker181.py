import resource_worker181 as a
import json,time,uuid
R=a.R/'measurements/lifecycle'/a.product;R.mkdir(parents=True,exist_ok=True)
for i in range(51):
 p=R/f'{i:02}.json'
 if p.exists():
  d=json.load(open(p))
  if d.get('success'):continue
  raise RuntimeError('Review failed lifecycle sample '+str(p))
 a.wait(a.c);s=None;row=dict(product=a.product,iteration=i,warmup=i==0,success=False)
 try:
  s=a.create();row['sandbox_id']=a.b.sid(s);a.b.save(p.with_suffix('.ledger'),[row['sandbox_id']])
  token=uuid.uuid4().hex;assert a.cmd(s,'echo '+token)==token
  row['delete_start_unix_ns']=time.time_ns();t=time.perf_counter_ns();a.b.kill(s);s=None;row['delete_ack_ms']=(time.perf_counter_ns()-t)/1e6
  state=a.wait(a.c);row['pool_after']=state;row['refill_wait_ms']=state['elapsed_ms'] if state['supported'] else None
  row['delete_through_refill_ms']=(time.perf_counter_ns()-t)/1e6 if state['supported'] else None
  row['success']=True
 finally:
  if s:a.b.kill(s)
  a.b.save(p,row);a.b.save(p.with_suffix('.ledger'),[])
 print(a.product,'lifecycle',i,'OK',flush=True)
