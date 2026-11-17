import sys,json,os,time,uuid
from pathlib import Path
M=Path('/opt/bench108');sys.path.insert(0,str(M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'));import vm_rpc
r=json.loads((M/'data/fork/adapter-state.json').read_text());sid=min((v['pool_ready_ns'],k) for k,v in r.items() if v.get('pool_state')=='ready')[1];record=r[sid]
z=vm_rpc.execute(record['vsock_socket'],['/bin/sh','-c','cat > /run/kuasar-image-mount && chmod 700 /run/kuasar-image-mount'],(M/'tools/fork-opt3-108/diag-mount').read_bytes());assert z['exit_code']==0
os.environ.update(E2B_API_KEY=(M/'deploy/fork/api-key').read_text().strip(),E2B_API_URL='http://127.0.0.1:18887',E2B_SANDBOX_URL='http://127.0.0.1:18887',NO_PROXY='*')
from e2b import Sandbox
def stat():
 x=Path('/proc/'+str(record['pid'])+'/stat').read_text().rsplit(')',1)[1].split()
 return {'minor_faults':int(x[7]),'major_faults':int(x[9]),'utime_ticks':int(x[11]),'stime_ticks':int(x[12])}
before=stat();s=Sandbox.create('base',timeout=60)
try:
 assert s.sandbox_id==sid
 created=stat();marker='DIAG_'+uuid.uuid4().hex;z=s.commands.run('printf '+marker,user='root');assert z.stdout==marker
 printed=stat()
 (M/'results/fork-opt3-108/diagnostic.json').write_text(json.dumps({'sid':sid,'before':before,'created':created,'printed':printed,'note':'one diagnostic, not a benchmark median; VMM aggregate proc counters'},indent=2))
finally:s.kill()
