"""Recover actual stage evidence from the unit's append log, without rerunning samples."""
from pathlib import Path
import bisect,hashlib,json,re
B=Path('/home/hong/src/research/sevenway-current-20261126/six')
source=Path('/var/log/bench-python113-refill-scale-fixed.log')
entries=[]
with source.open() as f:
 for line in f:
  if 'VM_FORK stage ' in line:
   m=re.search(r'\bmono_ns=(\d+)',line)
   if m:entries.append((int(m[1]),line))
  elif 'E2B_TIMING ' in line:
   try:d=json.loads(line.split('E2B_TIMING ',1)[1]);entries.append((d['started_ns'],line))
   except (ValueError,KeyError):pass
entries.sort(key=lambda e:e[0]);times=[t for t,_ in entries]
for p in (B/'results/live-formal').glob('*/*/result.json'):
 r=json.loads(p.read_text());assert r['success']
 lines=''.join(s for _,s in entries[bisect.bisect_left(times,r['start_ns']):bisect.bisect_right(times,r['exec_done_ns'])])
 assert 'VM_FORK stage ' in lines and 'E2B_TIMING ' in lines,p
 out=p.parent/'host.log'
 if out.exists() and not (p.parent/'host-journal.log').exists():out.rename(p.parent/'host-journal.log')
 out.write_text(lines)
 (p.parent/'log-provenance.json').write_text(json.dumps({'source':str(source),'capture':'retrospective monotonic-window extraction from original append log','start_ns':r['start_ns'],'end_ns':r['exec_done_ns'],'sha256':hashlib.sha256(lines.encode()).hexdigest()},indent=2))
print('Recovered all 51 measured/warmup log windows from original events.')
