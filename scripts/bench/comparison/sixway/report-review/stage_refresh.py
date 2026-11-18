from pathlib import Path
import shutil,json
O=Path('/home/hong/src/research/report-revision-113');B=Path('/home/hong/src/research/report-review-113')
files=['run_matrix.py','mode_worker.py','cache_state.py','live_fork.py','analyze_live.py','summarize_modes.py','snapshot_bench.py','pool_memory.py','read_resource_suite.py','verify_disk_backing.py','verify_images.py','final_audit.py']
for n in files:
 s=(O/n).read_text().replace(str(O),str(B));(B/n).write_text(s)
for p in (B/'tools').glob('*.py'):
 p.write_text(p.read_text().replace(str(O),str(B)))
for n in ['remote-cache.json','kuasar-off-native.json','kuasar-uffd-native.json','host-current.json','carrier-accounting.json','nested-runtime-provenance.json','nested-recovery.json','image-verification.json','disk-backing-verification.json']:
 shutil.copy2(O/n,B/n)
for n in ['bin','native']:
 if not (B/n).exists():(B/n).symlink_to(O/n)
# All regenerated results get independent files, never write through older results.
# growth remains read-only during paced tests for their memory guard; unlink after paced completion.
(B/'refresh-staged.json').write_text(json.dumps({'ready':True,'source':str(O),'output':str(B),'resource_rerun':'all six / Python only','startup':'50 measured + one warmup per group'}))
