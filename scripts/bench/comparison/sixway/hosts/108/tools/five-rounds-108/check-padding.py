from pathlib import Path
import json,hashlib
m=Path('/opt/bench108');r=m/'results/five-rounds-108';p=json.loads((r/'round5/preparation.json').read_text());roots={'node':'bb8cd20f7ab54d4cbe081009a7ba7e697928fb00aa7cd7a49fd0bf6769b20ec1','ruby':'b069325c4b4d59f6de0904c2556c30582d51e87ad278602e4e762505052519f7'};out={}
for l,key in roots.items():
 src=m/'data/fork/language-images'/key/'root.ext4';disk=Path(p[l]['directory'])/'disk-1.raw';h=hashlib.sha256();tail=0
 with disk.open('rb') as f:
  left=src.stat().st_size
  while left:
   b=f.read(min(4*1024*1024,left));assert b;h.update(b);left-=len(b)
  zero=bytes(4*1024*1024)
  for b in iter(lambda:f.read(len(zero)),b''):
   assert b==zero[:len(b)],(l,tail);tail+=len(b)
 with src.open('rb') as f:expected=hashlib.file_digest(f,'sha256').hexdigest()
 assert h.hexdigest()==expected
 out[l]={'source_bytes':src.stat().st_size,'fork_disk_bytes':disk.stat().st_size,'source_and_fork_prefix_sha256':expected,'zero_padding_bytes':tail,'image_payload_identical':True}
(r/'image-padding-validation.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
