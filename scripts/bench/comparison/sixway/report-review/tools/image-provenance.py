from pathlib import Path
import hashlib,json,urllib.request
B=Path('/home/hong/src/research/report-review-113');spec=json.loads((B/'tools/languages.example.json').read_text())['_languages'];out={}
for language,item in spec.items():
 repo='base' if language=='python' else language;root='http://127.0.0.1:5000/v2/e2b/'+repo
 req=urllib.request.Request(root+'/manifests/'+item['digest'],headers={'Accept':'application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'})
 manifest=urllib.request.urlopen(req).read();assert 'sha256:'+hashlib.sha256(manifest).hexdigest()==item['digest'];m=json.loads(manifest)
 cfg=urllib.request.urlopen(root+'/blobs/'+m['config']['digest']).read();assert 'sha256:'+hashlib.sha256(cfg).hexdigest()==m['config']['digest']
 d=json.loads(cfg);out[language]={'digest':item['digest'],'config_digest':m['config']['digest'],'oci_config':d['config'],'image':item['image'],'architecture':d['architecture']};assert d['architecture']=='amd64'
(B/'results/image-provenance.json').write_text(json.dumps(out,indent=2));print({k:v['digest'] for k,v in out.items()})
