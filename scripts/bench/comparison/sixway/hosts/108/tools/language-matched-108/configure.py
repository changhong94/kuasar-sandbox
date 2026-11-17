from pathlib import Path
import json
M=Path('/opt/bench108');R=M/'results/language-matched-108';T=M/'tools/language-matched-108';imports=json.loads((R/'mlink-import.json').read_text());catalog=json.loads((M/'deploy/fork/images.json').read_text())
for language in ['node','ruby']:
 cfg=json.loads((M/'tools/python-matched-audit-108/config.json').read_text());cfg['_image_digest']=catalog[language]['manifest'];cfg['_language']=language;cfg['_binary']='/usr/local/bin/'+language;cfg['_flag']='-e';cfg['_code']='console.log(process.argv[1])' if language=='node' else '$stdout.sync = true; puts ARGV[0]'
 cfg['_env']=['HOME=/root','USER=root','LOGNAME=root',*catalog[language]['oci_config']['Env']]
 cfg['kuasar-fork']['template']=language;cfg['kuasar-mlink']['template']=imports[language]['template'];cfg['kuasar-mlink']['netns']='b108-mlink-lang';cfg['kuasar-mlink']['ctl']=[x.replace('/data/mlink/','/data/mlink-lang/') for x in cfg['kuasar-mlink']['ctl']]
 (T/(language+'.json')).write_text(json.dumps(cfg,indent=2))
