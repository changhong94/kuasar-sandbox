import os,sys,json,time,shlex,uuid
from pathlib import Path
M=Path('/opt/bench108');sys.path.insert(0,str(M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'));import vm_rpc
url='http://127.0.0.1:18887';os.environ.update(E2B_API_KEY=(M/'deploy/fork/api-key').read_text().strip(),E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
from e2b import Sandbox
s=Sandbox.create('base',timeout=120);report={}
try:
 marker='STREAM_'+uuid.uuid4().hex;seen=[];start=time.perf_counter()
 code='import sys,time; print(sys.argv[1],flush=True); time.sleep(1)'
 r=s.commands.run(shlex.join(['exec','/usr/local/bin/python3','-c',code,marker]),user='root',timeout=10,on_stdout=lambda x:seen.append((time.perf_counter(),x)))
 end=time.perf_counter();first=next(t for t,x in seen if marker in x)
 assert r.exit_code==0 and end-first>.75,(r,end-first)
 info=vm_rpc.admin(M/'deploy/fork/admin.sock','sandbox-get',sandbox_id=s.sandbox_id)['live_fork'];path=info['vsock_socket']
 events=list(vm_rpc.execute_stream(path,['/bin/busybox','sh','-c','printf out; printf err >&2; exit 7']))
 assert b''.join(x.get('stdout',b'') for x in events)==b'out'
 assert b''.join(x.get('stderr',b'') for x in events)==b'err'
 assert events[-1]['exit_code']==7
 def fds():
  z=vm_rpc.execute(path,['/bin/busybox','sh','-c','/bin/busybox ls /proc/1/fd | /bin/busybox wc -l']);assert z['exit_code']==0;return int(z['stdout'])
 before=fds()
 stream=vm_rpc.execute_stream(path,['/bin/busybox','sh','-c','/bin/busybox sleep .05; /bin/busybox head -c 1048576 /dev/zero'])
 assert next(stream)['pid']>0;stream.close();time.sleep(.3)
 after=fds();assert before==after,(before,after)
 report=dict(success=True,first_output_ms=(first-start)*1000,completion_ms=(end-start)*1000,output_precedes_exit_ms=(end-first)*1000,stderr_and_exit_preserved=True,guest_fd_before=before,guest_fd_after_disconnect=after)
finally:s.kill()
(M/'results/python-opt-108/stream-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
