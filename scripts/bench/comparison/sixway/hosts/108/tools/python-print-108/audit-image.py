from pathlib import Path
import subprocess,hashlib,json,os
r=Path('/opt/bench108/results/python-print-108');out={}
images={'fork':Path('/opt/bench108/assets/python-base-fork-opt3-v2.erofs'),'mlink':Path('/opt/bench108/data/mlink/node/objects/snapshots/snap_196zaf70nza0s5htpz569sxvt7/base/disk.raw')}
for name,image in images.items():
 root=r/('audit-mount-'+name);root.mkdir(exist_ok=True)
 filesystem=subprocess.check_output(['blkid','-p','-s','TYPE','-o','value',str(image)],text=True).strip()
 subprocess.run(['mount','-t',filesystem,'-o','ro,loop'+(',noload' if filesystem=='ext4' else ''),str(image),str(root)],check=True)
 try:
  files={}
  for path in [root/'usr/local/bin/python3.12',root/'usr/local/lib/libpython3.12.so.1.0',*(root/'usr/local/lib/python3.12').rglob('*')]:
   if path.is_file() and not path.is_symlink():files[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
  assert 'usr/local/bin/python3.12' in files and len(files)>100
  out[name]={'image':str(image),'python_files':files}
 finally:subprocess.run(['umount',str(root)],check=True);root.rmdir()
out['python_payload_identical']=out['fork']['python_files']==out['mlink']['python_files']
(r/'image-audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(python_payload_identical=out['python_payload_identical'],file_counts={n:len(out[n]['python_files']) for n in images})))
assert out['python_payload_identical']
