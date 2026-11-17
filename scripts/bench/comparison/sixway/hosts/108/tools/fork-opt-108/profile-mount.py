import sys,json,os
from pathlib import Path
m=Path('/opt/bench108');sys.path.insert(0,str(m/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'));import vm_rpc
records=json.loads((m/'data/fork/adapter-state.json').read_text());sid=min((r['pool_ready_ns'],s) for s,r in records.items() if r.get('pool_state')=='ready')[1];info=vm_rpc.admin(m/'deploy/fork/admin.sock','sandbox-get',sandbox_id=sid)['live_fork']
z=vm_rpc.execute(info['vsock_socket'],['/bin/sh','-c','cat > /run/kuasar-image-mount && chmod 700 /run/kuasar-image-mount'],(m/'tools/fork-opt-108/mount-profile').read_bytes());assert z['exit_code']==0
os.environ.update(E2B_API_KEY=(m/'deploy/fork/api-key').read_text().strip(),E2B_API_URL='http://127.0.0.1:18887',E2B_SANDBOX_URL='http://127.0.0.1:18887',NO_PROXY='*')
from e2b import Sandbox
s=Sandbox.create('base',timeout=60)
try:
 assert s.sandbox_id==sid
 z=vm_rpc.execute(info['vsock_socket'],['/bin/busybox','cat','/run/image-mount-profile.json']);assert z['exit_code']==0
 (m/'results/fork-opt-108/mount-internal.json').write_bytes(z['stdout']);print(z['stdout'].decode())
finally:s.kill()
