from pathlib import Path
import subprocess as sp,json,time,hashlib
P=Path('/home/hong/deploy/comparison/sixway');W=P/'mlink-matched-image';W.mkdir(exist_ok=False);t=time.monotonic()
oci=Path('/home/hong/deploy/kuasar-fork-research/matched-image-build/oci')
sp.run(['/home/hong/deploy/comparison/tools/umoci','unpack','--image',str(oci)+':base',str(W/'bundle')],check=True)
root=W/'bundle/rootfs';image=W/'python-base.erofs'
sp.run(['mkfs.erofs',str(image),str(root)],check=True)
size=Path('/home/hong/src/private/kuasar-mlink/test_deps/share/base.erofs').stat().st_size
assert image.stat().st_size<=size
with image.open('ab') as f:f.truncate(size)
image.chmod(0o644)
ctl=['nsenter','--net=/run/netns/bench113-m','/home/hong/src/private/kuasar-mlink/test_deps/bin/ttctl','--server','http://127.0.0.1:28080','--data-server','http://127.0.0.1:28081','--admin-server','http://127.0.0.1:28082','--config','/home/hong/data/mlink/client.json','--request-timeout','300']
def call(*a):return sp.check_output(ctl+list(a),text=True).strip()
old=Path('/home/hong/deploy/private-pilot/mlink-template').read_text().strip();(W/'old-prewarm.json').write_text(call('--json','template','prewarm','inspect',old))
template=call('template','import',str(image),'--name','sixway-python31214','--cpu-count','1','--memory-mb','2048','--disk-size-mb','1024','--scope','full');print('imported',template,flush=True);(W/'imported-template').write_text(template+'\n')
sid=None
try:
 sid=call('start',template,'--insecure','--timeout','300');(W/'owned-instance').write_text(sid+'\n')
 proof=call('exec',sid,'--insecure','--','/bin/sh','-c','command -v python3; python3 --version; cat /etc/os-release; printf READY');print(proof,flush=True);assert 'Python 3.12.14' in proof and 'Debian' in proof
 captured=template;(P/'mlink-template').write_text(captured+'\n')
 (W/'proof.txt').write_text(proof)
finally:
 if sid:call('delete',sid);(W/'owned-instance').unlink()
(W/'preparation.json').write_text(json.dumps({'original_template':old,'imported_template':template,'template':captured,'base_manifest_digest':'sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79','image_sha256':hashlib.file_digest(image.open('rb'),'sha256').hexdigest(),'preparation_ms':(time.monotonic()-t)*1000},indent=2))
