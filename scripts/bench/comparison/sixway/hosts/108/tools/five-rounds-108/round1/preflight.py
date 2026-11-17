from pathlib import Path
import json,subprocess,sys,time
M=Path('/opt/bench108');T=M/'tools/five-rounds-108/round1';R=M/'results/five-rounds-108/round1';name=sys.argv[1];cfg=json.loads((T/(name+'.json')).read_text());ctl=cfg['kuasar-mlink']['ctl']
def call(a):return subprocess.check_output(ctl+a,text=True,stderr=subprocess.PIPE,timeout=90).strip()
s=call(['start',cfg['kuasar-mlink']['template'],'--insecure','--timeout','120'])
try:
 cmd='command -v fincore; fincore --bytes --output RES,PAGES /usr/local/bin/'+name+'; echo __PROC__; for f in /proc/[0-9]*/comm; do cat "$f" 2>/dev/null; done'
 z=call(['exec',s,'--insecure','--user','root','--','/bin/bash','-l','-c',cmd]);print(z)
 (R/(name+'-mlink-pristine.txt')).write_text(z)
 assert name not in z.split('__PROC__')[1].splitlines()
finally:call(['delete',s])
