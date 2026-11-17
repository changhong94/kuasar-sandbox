import requests,json,hashlib,concurrent.futures as cf,os,time,shutil
from pathlib import Path
root=Path('/opt/bench108/data/fork/language-downloads');root.mkdir(exist_ok=True)
started=time.monotonic()
def pull(name,digest):
 s=requests.Session();s.verify='/etc/ssl/certs/ca-certificates.crt'
 token=s.get('https://auth.docker.io/token',params={'service':'registry.docker.io','scope':f'repository:library/{name}:pull'},timeout=30).json()['token']
 headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.manifest.v1+json'}
 base=f'https://registry-1.docker.io/v2/library/{name}'
 m=s.get(base+'/manifests/'+digest,headers=headers,timeout=30);m.raise_for_status();raw=m.content;assert hashlib.sha256(raw).hexdigest()==digest.split(':')[1]
 manifest=m.json();layout=root/name;blobs=layout/'blobs/sha256';blobs.mkdir(parents=True,exist_ok=True);(blobs/digest.split(':')[1]).write_bytes(raw)
 for desc in [manifest['config'],*manifest['layers']]:
  h=desc['digest'].split(':')[1];dst=blobs/h;size=desc['size']
  existing=list(Path('/opt/bench108/data/fork/language-images').glob('.import-*/oci/blobs/sha256/'+h))
  if existing:
   shutil.copyfile(existing[0],dst)
  elif size<1024*1024:
   r=s.get(base+'/blobs/'+desc['digest'],headers=headers,timeout=120);r.raise_for_status();dst.write_bytes(r.content)
  else:
   r=s.get(base+'/blobs/'+desc['digest'],headers=headers,stream=True,timeout=30);r.raise_for_status();url=r.url;r.close()
   fd=os.open(dst,os.O_CREAT|os.O_RDWR|os.O_TRUNC,0o600);os.ftruncate(fd,size)
   def part(start):
    end=min(start+1024*1024,size)-1
    for attempt in range(3):
     try:
      z=requests.get(url,headers={'Range':f'bytes={start}-{end}'},verify='/etc/ssl/certs/ca-certificates.crt',timeout=120)
      assert z.status_code==206 and z.headers['Content-Range']==f'bytes {start}-{end}/{size}',(z.status_code,z.headers.get('Content-Range'))
      data=z.content;assert len(data)==end-start+1;assert os.pwrite(fd,data,start)==len(data);return
     except Exception:
      if attempt==2:raise
   try:
    with cf.ThreadPoolExecutor(8) as pool:list(pool.map(part,range(0,size,1024*1024)))
    os.fsync(fd)
   finally:os.close(fd)
  with dst.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==h
  print(name,h[:12],size,flush=True)
 (layout/'oci-layout').write_text('{"imageLayoutVersion":"1.0.0"}')
 (layout/'index.json').write_text(json.dumps({'schemaVersion':2,'manifests':[{'mediaType':manifest['mediaType'],'digest':digest,'size':len(raw),'annotations':{'org.opencontainers.image.ref.name':'image'}}]}))
 return {'name':name,'layout':str(layout),'elapsed_s':time.monotonic()-started}
with cf.ThreadPoolExecutor(2) as pool:
 out=list(pool.map(lambda p:pull(*p),[('node','sha256:47725aca53d3295ec2d3be8f62726599b3033cc262edc2c7e429909b3ac599fc'),('ruby','sha256:51d211cdbd0b226c7bbae9a377ed5731eaf2acb728000096061c01d360ed213d')]))
(root/'download.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
