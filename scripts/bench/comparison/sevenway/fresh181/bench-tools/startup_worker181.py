import sys,json,os
from pathlib import Path
os.environ.update(NO_PROXY='*',no_proxy='*')
from baseline_startup import setup,sample
R=Path('/home/hong/codex-work/sevenway-fresh-181');product,lang,phase=sys.argv[1:];cfg=json.load(open(R/'tools/config.json'));c=cfg[product].copy();spec=cfg['_languages'][lang];c['template']=spec['templates'][product];cfg[product]=c;cfg['_language']=lang;cfg['_image_digest']=spec['digest']
c,Sandbox=setup(product,cfg);out=R/'measurements'/phase/lang/product;out.mkdir(parents=True,exist_ok=True)
for i in range(1 if phase=='preflight' else 51):
 p=out/f'{i:02d}.json'
 if p.exists():
  old=json.load(open(p))
  if old.get('success') and old.get('destroyed'):continue
  p.rename(p.with_name(p.name+'.failed-'+str(__import__('time').time_ns())))
 assert sample(product,cfg,p,c,Sandbox),p
 row=json.load(open(p));row.update(warmup=(i==0),phase=phase,iteration=i);p.write_text(json.dumps(row,indent=2));print(product,lang,i,'OK',flush=True)
