from pathlib import Path
import subprocess as sp,tarfile,json,hashlib,time,re,shutil,os
P=Path('/home/hong/deploy/kuasar-fork-research');W=P/'matched-image-build';D=Path('/home/hong/data/kuasar-fork');A=Path('/home/hong/deploy/comparison/assets/scoring-base.oci.tar');digest='sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79'
assert not W.exists();W.mkdir(parents=True);t=time.monotonic();oci=W/'oci';oci.mkdir()
with tarfile.open(A) as tar:
 idx=json.load(tar.extractfile('index.json'));assert idx['manifests'][0]['digest']==digest
 for m in tar:
  if m.name.startswith('blobs/sha256/') and m.isfile():assert hashlib.sha256(tar.extractfile(m).read()).hexdigest()==m.name.rsplit('/',1)[1]
 tar.extractall(oci,filter='data')
idx['manifests'][0]['annotations']={'org.opencontainers.image.ref.name':'base'};(oci/'index.json').write_text(json.dumps(idx))
sp.run(['/home/hong/deploy/comparison/tools/umoci','unpack','--image',str(oci)+':base',str(W/'bundle')],check=True)
root=W/'bundle/rootfs';old=W/'old-runtime-root';old.mkdir()
sp.run(['debugfs','-R','rdump / '+str(old),'/home/hong/src/research/sandbox_bench/deploy/e2b-deferred-network/guest/rootfs.ext4'],check=True,stdout=sp.DEVNULL)
def hashes():
 return {str(p.relative_to(root)):hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
before=hashes();added=[]
def copy(src,dst):
 assert not dst.exists(),str(dst)
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);added.append(str(dst.relative_to(root)))
for name in ['vmm-task','busybox','runc','ss','fork-probe']:copy(old/'usr/bin'/name,root/'usr/bin'/name)
for name in ['vmm-task','busybox','runc','ss','fork-probe']:
 for _ in range(8):
  z=sp.run(['chroot',str(root),'/usr/bin/ldd','/usr/bin/'+name],capture_output=True,text=True)
  missing=re.findall(r'^\s*(\S+)\s+=>\s+not found',z.stdout,re.M)
  if not missing:
   if z.returncode and 'not a dynamic executable' not in z.stderr+z.stdout:raise RuntimeError(z.stdout+z.stderr)
   break
  for lib in missing:
   matches=[p for p in old.rglob(lib) if p.is_file()];assert matches,lib
   src=matches[0];copy(src,root/src.relative_to(old))
 else:raise RuntimeError('unresolved runtime dependencies')
for name in ['lower','upper','newroot','proc','sys','dev','dev/pts','dev/shm','run','tmp','opt/container-rootfs']:(root/name).mkdir(parents=True,exist_ok=True)
for name in ['hosts','hostname','resolv.conf']:
 p=root/'etc'/name
 if not p.exists():p.write_text('')
after=hashes();assert all(after.get(k)==v for k,v in before.items()),'base image file changed'
version=sp.check_output(['chroot',str(root),'/usr/local/bin/python3','--version'],text=True).strip();assert version=='Python 3.12.14',version
image=W/'rootfs.ext4'
with image.open('xb') as f:f.truncate(512*1024**2)
sp.run(['mkfs.ext4','-q','-F','-d',str(root),str(image)],check=True)
record={'base_manifest_digest':digest,'base_config_digest':'sha256:ec7d6c95cd3692a2e2d228a8b1ca74e4025b54121fcc4c5da6f09cfa473315ad','source_archive':str(A),'source_archive_sha256':hashlib.file_digest(A.open('rb'),'sha256').hexdigest(),'python':version,'base_regular_files_verified_unchanged':len(before),'base_files':before,'added_runtime_files':added,'image_sha256':hashlib.file_digest(image.open('rb'),'sha256').hexdigest(),'build_ms':(time.monotonic()-t)*1000}
(W/'image-identity.json').write_text(json.dumps(record,indent=2));print(json.dumps({k:v for k,v in record.items() if k!='base_files'}),flush=True)
