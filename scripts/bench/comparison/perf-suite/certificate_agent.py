"""Fixed TB2 certificate work, separate calls or one submitted batch.

The original command bytes, expected failed step and original grader survive.
Batch mode measures a Python dispatcher plus fourteen bash processes explicitly;
its difference from SDK mode is NOT claimed as pure virtualization overhead.
"""
import hashlib
import json
import os
from pathlib import Path
import time
from fixed_certificate_agent import FixedCertificateAgent

class PerformanceCertificateAgent(FixedCertificateAgent):
    async def run(self,instruction,environment,context):
        if os.environ.get('PERF_CERT_MODE','separate')=='separate':
            return await super().run(instruction,environment,context)
        path=Path(os.environ['PERF_WORKSPACE'])/'certificate-replay-commands-v1.json'
        raw=path.read_bytes();commands=json.loads(raw)['commands']
        program='''import subprocess,time,json,hashlib
commands=json.load(open('/tmp/perf-certificate-commands.json'))['commands']
rows=[];start=time.perf_counter()
for i,cmd in enumerate(commands):
    t=time.perf_counter();q=subprocess.run(['bash','-c',cmd],capture_output=True,text=True)
    rows.append(dict(index=i,command_sha256=hashlib.sha256(cmd.encode()).hexdigest(),elapsed_ms=(time.perf_counter()-t)*1000,return_code=q.returncode,stdout=q.stdout,stderr=q.stderr))
    if i!=11 and q.returncode:break
print(json.dumps(dict(commands=rows,guest_batch_ms=(time.perf_counter()-start)*1000)))
'''
        await environment._sandbox.files.write('/tmp/perf-certificate-commands.json',raw,user='root')
        await environment._sandbox.files.write('/tmp/perf-certificate-batch.py',program,user='root')
        t=time.perf_counter();q=await environment.exec('python3 /tmp/perf-certificate-batch.py',timeout_sec=180,user='root')
        elapsed=(time.perf_counter()-t)*1000
        if q.return_code:raise RuntimeError(q.stderr)
        data=json.loads(q.stdout);rows=data['commands']
        data.update(workload_sha256=hashlib.sha256(raw).hexdigest(),elapsed_ms=elapsed,model_calls=0,mode='batch')
        (self.logs_dir/'fixed-replay.json').write_text(json.dumps(data,indent=2))
        assert len(rows)==14 and rows[11]['return_code']!=0
        assert all(r['return_code']==0 for r in rows if r['index']!=11)
