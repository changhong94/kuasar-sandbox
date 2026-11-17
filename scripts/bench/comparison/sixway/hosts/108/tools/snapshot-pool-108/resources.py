import json,sys,subprocess
from pathlib import Path
cg=subprocess.check_output(['systemctl','show','bench108-fork','-p','ControlGroup','--value'],text=True).strip()
pids=[int(x) for x in Path('/sys/fs/cgroup'+cg+'/cgroup.procs').read_text().split()]
rows=[]
for pid in pids:
 try:
  data={}
  for line in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines():
   if ':' in line:
    k,v=line.split(':',1)
    if k in ('Rss','Pss','Private_Dirty','Private_Clean'):data[k]=int(v.split()[0])
  data.update(pid=pid,comm=Path(f'/proc/{pid}/comm').read_text().strip(),fds=len(list(Path(f'/proc/{pid}/fd').iterdir())))
  rows.append(data)
 except FileNotFoundError:pass
out=dict(processes=len(rows),totals={k:sum(r.get(k,0) for r in rows) for k in ('Rss','Pss','Private_Dirty','Private_Clean','fds')},rows=rows)
Path(sys.argv[1]).write_text(json.dumps(out,indent=2));print(json.dumps(out['totals']))
