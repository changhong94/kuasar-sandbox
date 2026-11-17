import sys,os,json,shlex,io,tarfile
from pathlib import Path
M=Path('/opt/bench108');Q=M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b';sys.path.insert(0,str(Q));import vm_rpc as v
from e2b import Sandbox
url='http://127.0.0.1:18887';os.environ.update(E2B_API_KEY=(M/'deploy/fork/api-key').read_text().strip(),E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
R=M/'results/five-rounds-108/round4';lang=sys.argv[1];cfg=json.loads((M/'tools/tcp-template-opt-108'/f'{lang}.json').read_text());s=Sandbox.create(lang,timeout=180)
try:
 path=v.admin(M/'deploy/fork/admin.sock','sandbox-get',sandbox_id=s.sandbox_id)['live_fork']['vsock_socket']
 files=['/usr/bin/strace','/lib/x86_64-linux-gnu/libunwind-ptrace.so.0','/lib/x86_64-linux-gnu/libunwind-x86_64.so.8','/lib/x86_64-linux-gnu/libunwind.so.8','/lib/x86_64-linux-gnu/liblzma.so.5']
 buf=io.BytesIO()
 with tarfile.open(fileobj=buf,mode='w') as t:
  for f in files:t.add(str(Path(f).resolve()),arcname='exec-diagnostic/'+Path(f).name)
 z=v.execute(path,['/bin/busybox','tar','xf','-','-C','/run/image-root/tmp'],buf.getvalue());assert z['exit_code']==0,z
 cmd='cd /; '+shlex.join(['exec','/usr/bin/env','-i',*cfg['_env'],cfg['_binary'],cfg['_flag'],cfg['_code'],'READY_DIAGNOSTIC'])
 result=s.commands.run("LD_LIBRARY_PATH=/tmp/exec-diagnostic /tmp/exec-diagnostic/strace -f -ttt -T -o /tmp/exec.trace /bin/bash -l -c "+shlex.quote(cmd),user='root',timeout=60)
 z=v.execute(path,['/bin/busybox','cat','/run/image-root/tmp/exec.trace']);assert z['exit_code']==0;(R/f'{lang}-exec-strace.txt').write_bytes(z['stdout']);(R/f'{lang}-exec-diagnostic.json').write_text(json.dumps({'stdout':result.stdout,'stderr':result.stderr,'sid':s.sandbox_id,'command':cmd},indent=2));print(lang,result.stdout)
finally:s.kill()
