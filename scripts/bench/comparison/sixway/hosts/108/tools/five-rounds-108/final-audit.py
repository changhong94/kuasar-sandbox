from pathlib import Path
import json,hashlib,subprocess as sp,concurrent.futures
M=Path('/opt/bench108');R=M/'results/five-rounds-108';P=json.loads((R/'round5/preparation.json').read_text())
roots={'node':'bb8cd20f7ab54d4cbe081009a7ba7e697928fb00aa7cd7a49fd0bf6769b20ec1','ruby':'b069325c4b4d59f6de0904c2556c30582d51e87ad278602e4e762505052519f7'}
ids={'node':'snap_1yhmm8aqhx2ycn8270rqh932nh','ruby':'snap_79v03nfq6wmw41ws7n1j3y14v8'}
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
rows=[]
for l in roots:
 for kind,p in [('source',M/'data/fork/language-images'/roots[l]/'root.ext4'),('fork',Path(P[l]['directory'])/'disk-1.raw'),('mlink',M/'data/mlink-lang/node/objects/snapshots'/ids[l]/'base/disk.raw')]:rows.append((l,kind,p))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:hashes=list(pool.map(lambda row:{'language':row[0],'kind':row[1],'path':str(row[2]),'sha256':digest(row[2])},rows))
(R/'image-hashes.json').write_text(json.dumps(hashes,indent=2))
print(json.dumps(hashes),flush=True)
files=[M/'deploy/fork/bin/sandboxer',M/'deploy/fork/bin/cloud-hypervisor',M/'assets/fork-runtime-five-round5.ext4',M/'build/snapshot-pool/release/vmm-task']
report={'image_hashes':hashes,'deployed_hashes':{str(p):digest(p) for p in files},'original_mlink':sp.check_output(['systemctl','show','bench108-mlink','-p','MainPID','-p','ActiveEnterTimestamp'],text=True),'template_memory':[]}
for l,p in P.items():
 f=Path(p['directory'])/'memory-ranges';report['template_memory'].append({'template':l,'bytes':f.stat().st_size,'allocated_bytes':f.stat().st_blocks*512,'fincore':sp.check_output(['fincore','--bytes','--noheadings','--output','RES,SIZE',str(f)],text=True).strip()})
(R/'final-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
