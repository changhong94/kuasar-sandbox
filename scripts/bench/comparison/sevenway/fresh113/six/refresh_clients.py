from pathlib import Path
import json,subprocess,time
B=Path('/home/hong/src/research/sevenway-current-20261126/six');T=B/'tools';P='/home/hong/src/research/python-latest-113/venv/bin/python';c=json.loads((T/'config.json').read_text());(B/'private').mkdir(mode=0o700,exist_ok=True)
for product,src in [('kuasar-off','/home/hong/deploy/comparison/kuasar-state/access.json'),('kuasar-uffd','/home/hong/deploy/private-pilot/uffd-state/access.json')]:
 a=json.loads(Path(src).read_text());assert Path(a['work_dir']).exists();k=B/'private'/product;k.write_text(a['api_key']);k.chmod(0o600);c[product].update(key_file=str(k),ca_file=a['ca_file'],template=a['template_id']);c['_languages']['python']['templates'][product]=a['template_id']
(T/'config.json').write_text(json.dumps(c,indent=2));(T/'languages.example.json').write_text(json.dumps(c,indent=2))
for product in ['kuasar-off','kuasar-uffd']:
 for lang in ['node','ruby']:
  target=B/'results'/f'template-{product}-{lang}.json'
  if not target.exists():subprocess.run(['nsenter','--net=/run/netns/'+c[product]['netns'],P,str(T/'prepare-sdk.py'),product,lang],check=True)
  x=json.loads(target.read_text());assert x['digest']==c['_languages'][lang]['digest'];c['_languages'][lang]['templates'][product]=x['template'];(T/'config.json').write_text(json.dumps(c,indent=2))
print('Fresh tenant credentials and pinned templates ready')
