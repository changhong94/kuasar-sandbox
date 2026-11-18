"""Persistent pause/resume, distinct from fresh-template startup.

Each sample has a running stateful process and fsynced 32 MiB file. API save
latency excludes the subsequent storage-observation interval. Restores retain
natural post-save caches. No claim of equivalent cold post-reboot restore.
"""
import argparse,fcntl,hashlib,json,os,shlex,statistics,subprocess,sys,time,uuid
from pathlib import Path
B=Path('/home/hong/src/research/report-review-113');T=B/'tools';sys.path.insert(0,str(T))
import runner as b
import retained
from pool_gate import wait as pool_wait
from languages import print_command

KEEPER='''import os,time,hashlib
blob=os.urandom(32*1024*1024)
i=0
while True:
 i+=1
 print(os.getpid(),i,hashlib.sha256(blob).hexdigest(),flush=True)
 time.sleep(0.2)
'''

def observation(s):
 return b.cmd(s,'tail -n 1 /tmp/checkpoint-process.log').split()

def restored_print(s):
 native='NATIVE_'+uuid.uuid4().hex;printed='READY_'+uuid.uuid4().hex
 command,_=print_command('python',printed,native);chunks=[];times={}
 def receive(text):
  chunks.append(text);all_text=''.join(chunks)
  if 'ready_ns' not in times and native+'\n' in all_text:times['ready_ns']=time.monotonic_ns()
  if 'print_ns' not in times and printed+'\n' in all_text:times['print_ns']=time.monotonic_ns()
 if b.pr=='kuasar-mlink':
  import select,tempfile
  with tempfile.TemporaryFile() as err:
   with subprocess.Popen(b.ctl+['exec',s,'--insecure','--user','root','--','/bin/bash','-l','-c',command],stdout=subprocess.PIPE,stderr=err) as proc:
    try:
     deadline=time.monotonic()+90
     while True:
      remaining=deadline-time.monotonic()
      if remaining<=0 or not select.select([proc.stdout],[],[],remaining)[0]:raise TimeoutError('restore print')
      chunk=os.read(proc.stdout.fileno(),65536)
      if not chunk:break
      receive(chunk.decode())
     assert proc.wait(timeout=10)==0
    except BaseException:proc.kill();proc.wait();raise
 else:
  result=s.commands.run(command,user='root',timeout=90,on_stdout=receive)
  assert result.exit_code==0,result.stderr
 assert 'ready_ns' in times and 'print_ns' in times
 return times

def worker(product,out):
 b.pr=product;b.setup(product);out.mkdir(parents=True,exist_ok=False)
 for index in range(51):
  name='warmup' if index==0 else f'{index:02d}'
  row={'product':product,'index':index,'warmup':index==0,'success':False,
       'restore_cache':'natural post-save cache; no forced eviction',
       'snapshot_operation':'persistent pause; source stays stopped until explicit resume',
       'memory_payload_mib':32,'file_payload_mib':32}
  path=out/(name+'.json');s=None
  def save():b.save(path,row)
  try:
   row['pool_before']=pool_wait(b.c,64,600)
   s=b.create();row['sandbox_id']=b.sid(s);save()
   b.ready(s,'true','')
   io=json.loads(b.py(s,b.IO));row['file_sha256']=io[0]
   b.cmd(s,'nohup /usr/local/bin/python3 -u -c '+shlex.quote(KEEPER)+' >/tmp/checkpoint-process.log 2>/tmp/checkpoint-process.err </dev/null &')
   deadline=time.monotonic()+30
   while True:
    before=observation(s)
    if len(before)==3:break
    if time.monotonic()>deadline:raise TimeoutError('stateful process readiness')
    time.sleep(.05)
   row['process_before']=before
   row['before_snapshot']=retained.footprint(product)
   row['snapshot_request_ns']=time.monotonic_ns()
   b.pause(s)
   row['snapshot_ack_ns']=time.monotonic_ns()
   row['snapshot_ms']=(row['snapshot_ack_ns']-row['snapshot_request_ns'])/1e6
   row['after_snapshot']=retained.footprint(product)
   if row['before_snapshot']['valid'] and row['after_snapshot']['valid']:
    row['snapshot_disk_increment_bytes']=row['after_snapshot']['unique_extent_bytes']-row['before_snapshot']['unique_extent_bytes']
   row['restore_request_ns']=time.monotonic_ns()
   s=b.resume(s)
   row['restore_api_ns']=time.monotonic_ns()
   row.update(restored_print(s))
   for label in ['restore_api','ready','print']:
    row[label+'_ms']=(row[label+'_ns']-row['restore_request_ns'])/1e6
   row['explicit_paused_observation_ms']=(row['restore_request_ns']-row['snapshot_ack_ns'])/1e6
   deadline=time.monotonic()+10
   while True:
    after=observation(s)
    assert len(after)==3 and after[0]==before[0] and after[2]==before[2],(before,after)
    if int(after[1])>int(before[1]):break
    if time.monotonic()>deadline:raise TimeoutError('restored process did not continue')
    time.sleep(.05)
   assert b.cmd(s,'sha256sum /tmp/fiveway.bin').split()[0]==io[0]
   row.update(process_after=after,process_state_verified=True,file_state_verified=True,success=True)
  except Exception as e:
   row['error']=repr(e);raise
  finally:
   if s is not None:
    try:
     b.kill(s);row['destroyed']=True
     row['pool_after']=pool_wait(b.c,64,600)
    except Exception as e:row['destroyed']=False;row['cleanup_error']=repr(e)
   save()
  assert row['success'] and row['destroyed']
  print(product,index,row['snapshot_ms'],row['ready_ms'],row['print_ms'],flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--worker');args=p.parse_args()
 if args.worker:worker(args.worker,B/'results/snapshots'/args.worker)
 else:
  with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   for product in ['kuasar-fork','kuasar-mlink','agentenv','cube','kuasar-off','kuasar-uffd']:
    subprocess.run(['nsenter','--net=/run/netns/'+b.ns[product],sys.executable,__file__,'--worker',product],check=True)
