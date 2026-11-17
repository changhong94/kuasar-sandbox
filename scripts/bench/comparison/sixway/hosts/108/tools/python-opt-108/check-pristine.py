import os,sys,json
from pathlib import Path
M=Path('/opt/bench108');sys.path.insert(0,str(M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'));import vm_rpc
key=(M/'deploy/fork/api-key').read_text().strip();url='http://127.0.0.1:18887';os.environ.update(E2B_API_KEY=key,E2B_API_URL=url,E2B_SANDBOX_URL=url,NO_PROXY='*')
from e2b import Sandbox
s=Sandbox.create('base',timeout=120)
try:
 info=vm_rpc.admin(M/'deploy/fork/admin.sock','sandbox-get',sandbox_id=s.sandbox_id)['live_fork']
 cmd='''/bin/busybox find /run/image-root/usr/local/lib/python3.12 -name '*.pyc'; echo __PROCESSES__; for f in /proc/[0-9]*/comm; do c=$(/bin/busybox cat "$f" 2>/dev/null) || continue; case "$c" in python*) echo "$c";; esac; done'''
 z=vm_rpc.execute(info['vsock_socket'],['/bin/busybox','sh','-c',cmd]);assert z['exit_code']==0;pyc,processes=z['stdout'].decode().split('__PROCESSES__\n');assert not pyc.strip() and not processes.strip(),z
 report=dict(success=True,pyc_files_before_first_command=0,python_processes_before_first_command=0,guest_audit_program='trusted busybox only')
finally:s.kill()
(M/'results/python-opt-108/pristine.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
