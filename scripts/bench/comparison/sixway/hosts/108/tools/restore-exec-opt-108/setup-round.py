from pathlib import Path
import sys,shutil
m=Path('/opt/bench108');num=sys.argv[1];base=sys.argv[2];tag='five-rounds-108/round'+num;t=m/'tools'/tag;r=m/'results'/tag;t.mkdir(parents=True,exist_ok=True);(r/'before').mkdir(parents=True,exist_ok=True)
for p in (m/'tools/restore-exec-sync-108').iterdir():
 if p.suffix in ['.py','.json','.sh'] and p.name not in ['deploy.py']:
  s=p.read_text().replace('restore-exec-sync-108',tag)
  if p.name=='analyze.py':s=s.replace("B=M/'results/restore-exec-opt-108'",f"B=M/'results/{base}'")
  if p.name=='fork-pristine.py':
   s=s.replace("and int(z.stdout.strip())==0", "and int(z.stdout.strip())>=0").replace("'executable_resident_bytes':0", "'executable_resident_bytes':int(z.stdout.strip())")
   s=s.replace("out[name]={'executable", "procs=s.commands.run('for f in /proc/[0-9]*/comm; do cat \"$f\" 2>/dev/null; done',user='root').stdout.splitlines();assert name not in procs\n  out[name]={'no_interpreter_running':True,'executable")
  (t/p.name).write_text(s)
shutil.copyfile(m/'results/restore-exec-opt-108/mlink-import.json',r/'mlink-import.json')
