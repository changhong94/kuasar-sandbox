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
 binary=Path('/opt/bench108/tools/no-python-warm-108/residency').read_bytes()
 z=vm_rpc.execute(info['vsock_socket'], ['/bin/busybox','sh','-c','/bin/busybox cat > /run/residency; /bin/busybox chmod 700 /run/residency'],binary);assert z['exit_code']==0
 paths=json.loads(Path('/opt/bench108/results/no-python-warm-108/before-images.json').read_text())['base']['startup_read_files']
 z=vm_rpc.execute(info['vsock_socket'],['/run/residency',*['/run/image-root'+p for p in paths]]);assert z['exit_code']==0
 residency=[dict(path=line.split()[0],resident_pages=int(line.split()[1]),total_pages=int(line.split()[2])) for line in z['stdout'].decode().splitlines()]
 assert all(r['resident_pages']==0 for r in residency),residency
 report=dict(residency=residency,success=True,pyc_files_before_first_command=0,python_processes_before_first_command=0,guest_audit_program='trusted busybox and static mincore helper; no interpreter')
finally:s.kill()
(M/'results/no-python-warm-108/pristine.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
