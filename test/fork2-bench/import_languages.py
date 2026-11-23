#!/usr/bin/env python3
"""Import existing pinned Node/Ruby roots using a private, read-only mount."""
import base64,hashlib,json,os,pathlib,subprocess,time
root=pathlib.Path('/srv/fork2');data=root/'data'
assert os.readlink('/proc/self/ns/mnt')!=os.readlink('/proc/1/ns/mnt')
images=json.loads(pathlib.Path('/opt/bench108/deploy/fork/images.json').read_text())
for name in ('node','ruby'):
 row=images[name].copy();start=time.monotonic();src=pathlib.Path(row['disk'])
 digest=hashlib.sha256()
 with src.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):digest.update(chunk)
 assert digest.hexdigest()==row['sha256']
 mount=data/'import-mount';mount.mkdir(exist_ok=True);subprocess.run(['mount','-o','loop,ro,noload',str(src),str(mount)],check=True)
 try:
  loc='bench-image-'+name;h=hashlib.sha256(loc.encode()).hexdigest();dst=data/'publications'/h[:2]/h[2:4]/loc;dst.mkdir(parents=True,exist_ok=True)
  cfg=data/'import-config.json';cfg.write_text(json.dumps({'config':row['oci_config']}));out=dst/'root.image'
  subprocess.run([str(root/'bin/flatten-ctl'),'export','--no-progress','--runtime-config',str(cfg),'--output',str(out),str(mount)],check=True)
  with out.open('rb') as f:os.fsync(f.fileno())
  markers=[x for x in subprocess.check_output(['tar','-tf',str(out)],text=True).splitlines() if x.startswith('.kuasar.digest.')];assert len(markers)==1
  ref='file://root.image@digest:'+markers[0].split('.')[-1]+'@location:'+loc
  row.update(template_id='e2b-img-'+base64.urlsafe_b64encode(ref.encode()).decode().rstrip('='),preparation_ms=(time.monotonic()-start)*1000,logical_bytes=out.stat().st_size)
  (data/'registry'/(name+'.json')).write_text(json.dumps(row,indent=2));print(json.dumps({'language':name,'digest':row['manifest'],'preparation_ms':row['preparation_ms']}),flush=True)
 finally:subprocess.run(['umount',str(mount)],check=True)
