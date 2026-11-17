from pathlib import Path
import subprocess as sp,json,hashlib,platform
B=Path('/home/hong/src/research/sixway-aligned-20261117');F=Path('/home/hong/src/research/python-latest-113');d=dict(uname=platform.uname()._asdict(),cpu=json.loads(sp.check_output(['lscpu','-J'],text=True)),meminfo=Path('/proc/meminfo').read_text(),artifacts={})
for p in [F/'deploy/fork/bin/cloud-hypervisor',F/'deploy/fork/bin/vmm-sandboxer',F/'assets/python-base-fork-opt3-v2.erofs',F/'assets/fork-runtime-python-stream.ext4']:
 if p.exists():
  h=hashlib.sha256()
  with p.open('rb') as f:
   while data:=f.read(1024*1024):h.update(data)
  d['artifacts'][str(p)]=dict(sha256=h.hexdigest(),bytes=p.stat().st_size)
d['timing_note']='All primary elapsed timings are monotonic on 113. Do not align 108 filesystem timestamps with 113 event clocks.'
(B/'results/host-manifest.json').write_text(json.dumps(d,indent=2))
