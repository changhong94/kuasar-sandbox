from pathlib import Path
import json,os
B=Path('/home/hong/src/research/sixway-aligned-20261117');c=json.loads(Path('/home/hong/src/research/sixway-formal-python-113/tools/config.json').read_text());(B/'private').mkdir(exist_ok=True,mode=0o700)
for n in ['kuasar-off','kuasar-uffd']:
 p=Path('/home/hong/deploy/comparison/kuasar-state/access.json' if n=='kuasar-off' else '/home/hong/deploy/private-pilot/uffd-state/access.json');d=json.loads(p.read_text());key=B/'private'/n;key.write_text(d['api_key']);key.chmod(0o600)
 c[n].update(key_file=str(key),template=d['template_id'],ca_file=d['ca_file'])
 c[n]['create_kwargs']['metadata']['kuasar-sandbox.resource']=json.dumps({'capacity':{'cpu':2,'memory':'2048MiB'},'allocatable':{'cpu':2,'memory':'2048MiB'}})
c['agentenv']['template']='aligned-python-2cpu-v3'
c['cube']['template']=json.loads((B/'results/cube-template.log').read_text())['job']['template_id']
c['kuasar-mlink']['template']=json.loads((B/'results/mlink-template.json').read_text())['template'];c['kuasar-mlink']['pool_kind']='mlink';c['kuasar-fork']['pool_kind']='fork'
c['_profile']={'vcpus':2,'memory_mib':2048,'startup_pool_capacity':2,'warmup_samples':1,'startup_samples':50,'concurrency':1,'cache_policy':'no global cache reset; no guest Python in template preparation or training','readiness':'native shell marker then fresh Python in same exec stream; internal server ready separately where exposed','pool_unsupported':['kuasar-off','kuasar-uffd','cube','agentenv']}
(B/'tools/config.json').write_text(json.dumps(c,indent=2))
