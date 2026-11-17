from pathlib import Path
import subprocess as s,json,time,os,shutil,re,urllib.request,hashlib
B=Path('/home/hong/src/research/sixway-languages-20261117');F=Path('/home/hong/src/research/python-latest-113');P=F/'deploy/fork';backup=B/'backups/fork';backup.mkdir(exist_ok=False)
# The reset script rejects assigned sandboxes and drains only its own pool.
for name in ['config.toml','supervisor.py','images.json']:
 shutil.copyfile(P/name,backup/name)
for name in ['sandboxer','cloud-hypervisor']:shutil.copyfile(P/'bin'/name,backup/name)
s.run(['env','POOL_RESET_STOPPED=1','python3','/home/hong/src/research/sixway-aligned-20261117/tools/reset-fork.py'],check=True)
old=F/'data/fork/snapshot-templates'
if old.exists():old.rename(old.with_name('templates-before-languages-'+str(time.time_ns())))
old.mkdir()
for name in ['sandboxer','cloud-hypervisor']:
 new=P/'bin'/(name+'.next');shutil.copyfile(B/'assets'/name,new);new.chmod(0o755)
 with new.open('rb') as f:os.fsync(f.fileno())
 new.replace(P/'bin'/name)
cfg=(P/'config.toml').read_text();cfg=re.sub(r'image_path="[^"]+"','image_path="'+str(B/'assets/fork-runtime-latest-v2.ext4')+'"',cfg);assert 'vcpus=2' in cfg;(P/'config.toml').write_text(cfg)
sv=(P/'supervisor.py').read_text().replace("'cpu':1,","'cpu':2,");(P/'supervisor.py').write_text(sv)
images=json.loads((backup/'images.json').read_text());prov=json.loads((B/'results/image-provenance.json').read_text())
for lang in ['python','node','ruby']:
 key='base' if lang=='python' else lang
 if lang!='python':
  img=json.loads((B/'assets'/lang/'image.json').read_text());images[key]={k:img[k] for k in ['sha256','manifest']};images[key]['disk']=str(B/'assets'/lang/'root.ext4')
 conf=prov[lang]['oci_config'];conf.update(Entrypoint=[],Cmd=['/bin/sleep','infinity'],User='0',WorkingDir='/')
 images[key]['oci_config']=conf;images[key]['startup_read_files']=[]
(P/'images.json').write_text(json.dumps(images,indent=2))
drop=Path('/etc/systemd/system/bench-python113-fork.service.d');drop.mkdir(exist_ok=True)
(drop/'languages.conf').write_text('[Service]\nEnvironment=E2B_TEMPLATE_POOL_SIZE=2\nEnvironment=E2B_TEMPLATE_METADATA=1\nEnvironment=E2B_TEMPLATE_READ_CACHE_BYTES=536870912\nEnvironment=CH_RESTORE_TIMING=1\n')
s.run(['systemctl','daemon-reload'],check=True);start=time.monotonic_ns();s.run(['systemctl','start','bench-python113-fork'],check=True)
for _ in range(1200):
 try:
  req=urllib.request.Request('http://127.0.0.1:18887/template-pool',headers={'X-API-Key':(P/'api-key').read_text().strip()});d=json.load(urllib.request.urlopen(req,timeout=2))
  if d['ready']==2 and d['assigned']==0 and not d['preparing']:break
 except OSError:pass
 if s.run(['systemctl','is-failed','--quiet','bench-python113-fork']).returncode==0:raise RuntimeError('fork service failed')
 time.sleep(.2)
else:raise RuntimeError('fork pool did not become ready')
row={'service_start_to_ready_ms':(time.monotonic_ns()-start)/1e6,'pool':d,'image_templates':json.loads((F/'data/fork/adapter-state.json.snapshot-preparation.json').read_text()),'generic_file_cache_limit_bytes':536870912,'language_training':False}
(B/'results/fork-preparation.json').write_text(json.dumps(row,indent=2));print(json.dumps(row),flush=True)
