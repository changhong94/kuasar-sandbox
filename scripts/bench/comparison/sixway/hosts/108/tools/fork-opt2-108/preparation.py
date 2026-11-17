import json,sys,tempfile,time
from pathlib import Path
M=Path('/opt/bench108');sys.path.insert(0,str(M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'))
from slot_disk import SlotDisks
catalog=json.loads((M/'deploy/fork/images.json').read_text())
with tempfile.TemporaryDirectory(prefix='import-cost-',dir=M/'data/fork') as tmp:
 started=time.monotonic();s=SlotDisks(Path(tmp)/'slots',catalog)
 report={'cold_cache_import_and_verification_ms':(time.monotonic()-started)*1000,'files':len(catalog),'logical_bytes':sum(p.stat().st_size for p in s.cache.glob('*.raw')),'allocated_bytes':sum(p.stat().st_blocks*512 for p in s.cache.glob('*.raw')),'note':'one preparation measurement; includes disk copy and SHA256; not a VM/request benchmark'}
 (M/'results/fork-opt2-108/import-preparation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
