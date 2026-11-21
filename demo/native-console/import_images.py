#!/usr/bin/env python3
"""Convert existing immutable demo image disks without changing the old service.
Run in a private mount namespace; mount each source read-only with no journal replay.
"""
import base64,hashlib,json,os,pathlib,subprocess,tarfile,time
ROOT=pathlib.Path('/srv/forklab-native');DATA=ROOT/'data'
assert os.readlink('/proc/self/ns/mnt')!=os.readlink('/proc/1/ns/mnt'),'private mount namespace required'
def run(args):return subprocess.run(list(map(str,args)),check=True)
def save(path,value):
 tmp=path.with_suffix('.tmp')
 with tmp.open('w') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path);fd=os.open(path.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
for src in sorted(pathlib.Path('/srv/forklab/data/registry').glob('*.json')):
 old=json.loads(src.read_text());ident=old['id'];state=DATA/'registry'/src.name
 if state.exists() and json.loads(state.read_text()).get('state')=='ready':continue
 row={k:old[k] for k in ('id','name','manifest','source','compressed_bytes')};row['state']='building';save(state,row)
 start=time.monotonic();mount=DATA/'import-mount';mount.mkdir(exist_ok=True)
 try:
  assert old['state']=='ready'
  run(['mount','-o','loop,ro,noload',old['disk'],mount])
  cfg=DATA/'import-config.json';cfg.write_text(json.dumps({'config':old['oci_config']}))
  location='console-image-'+ident;sha=hashlib.sha256(location.encode()).hexdigest();dest=DATA/'publications'/sha[:2]/sha[2:4]/location;dest.mkdir(parents=True,exist_ok=True)
  output=dest/'root.image';tmp=dest/'root.image.tmp'
  run([ROOT/'bin/flatten-ctl','export','--no-progress','--runtime-config',cfg,'--output',tmp,mount])
  with tmp.open('rb') as f:os.fsync(f.fileno())
  os.replace(tmp,output);fd=os.open(dest,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
  markers=[n for n in subprocess.check_output(['tar','-tf',str(output)],text=True).splitlines() if n.startswith('.kuasar.digest.')]
  assert len(markers)==1
  ref='file://root.image@digest:'+markers[0].split('.')[-1]+'@location:'+location
  row.update(state='ready',logical_bytes=output.stat().st_size,allocated_bytes=output.stat().st_blocks*512,template_id='e2b-img-'+base64.urlsafe_b64encode(ref.encode()).decode().rstrip('='),preparation_ms=(time.monotonic()-start)*1000,conversion='read-only ext4 rootfs + original OCI config',source_disk_sha256=old['sha256'])
  save(state,row)
 except Exception as e:row.update(state='failed',error=str(e));save(state,row);raise
 finally:run(['umount',mount])
