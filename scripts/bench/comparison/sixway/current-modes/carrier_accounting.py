"""Final active native closure only; excludes obsolete export intermediates."""
from pathlib import Path
import json,os,statistics
B=Path('/home/hong/src/research/report-revision-113');rows=[]
for language in ('python','node','ruby'):
 for product in ('kuasar-fork','kuasar-off','kuasar-uffd'):
  def samples(mode):
   data=[json.loads((B/f'results/matrix/{language}/{product}/{mode}/{i:02d}.json').read_text()) for i in range(1,51)]
   assert all(x['success'] and x['cache_preparation']['verified'] for x in data)
   return data
  warm=samples('local_warm');cold=samples('local_cold');paths=[Path(x['path']) for x in warm[0]['cache_preparation']['after']]
  expected=set(map(str,paths))
  for r in warm+cold:assert {x['path'] for x in r['cache_preparation']['after']}==expected
  page=os.sysconf('SC_PAGE_SIZE')
  resident=lambda data:[sum(x['resident_pages'] for x in r['cache_preparation']['after'])*page for r in data]
  wr=resident(warm);cr=resident(cold)
  row={'product':product,'language':language,'logical_bytes':sum(p.stat().st_size for p in paths),'allocated_bytes':sum(p.stat().st_blocks*512 for p in paths),'warm_resident_bytes':statistics.median(wr),'cold_resident_bytes':statistics.median(cr),'warm_resident_range_bytes':[min(wr),max(wr)],'cold_resident_range_bytes':[min(cr),max(cr)],'files':[dict(path=str(p),logical_bytes=p.stat().st_size,allocated_bytes=p.stat().st_blocks*512) for p in paths],'configured_guest_ram_bytes':2*1024**3,'residency_scope':'mincore after per-request conditioning, before the create request; page-rounded; 50 samples'}
  assert max(cr)==0
  rows.append(row)
(B/'carrier-accounting.json').write_text(json.dumps({'rows':rows,'allocated_scope':'sum st_blocks*512 for final carrier closure only; not a physical extent union'},indent=2))
