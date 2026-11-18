from pathlib import Path
import shutil,json,hashlib,subprocess,time
B=Path('/home/hong/src/research/report-review-113');repo=Path('/home/hong/src/research/report-revision-113/bench');out=repo/'scripts/bench/comparison/sixway/report-review'
assert subprocess.check_output(['git','-C',str(repo),'branch','--show-current'],text=True).strip()=='sandbox_fork_staging'
out.mkdir(parents=True,exist_ok=True)
for p in B.glob('*.py'):shutil.copy2(p,out/p.name)
for p in B.glob('*.block'):shutil.copy2(p,out/p.name)
for p in B.glob('*.c'):shutil.copy2(p,out/p.name)
for p in (B/'tools').glob('*.py'):
 (out/'tools').mkdir(exist_ok=True);shutil.copy2(p,out/'tools'/p.name)
# Config contains credential FILE PATHS; never archive credential file contents.
cfg=json.loads((B/'tools/config.json').read_text())
for p,c in cfg.items():
 if isinstance(c,dict):
  assert not any(k in c for k in ('api_key','password','token','secret')),p
(out/'tools/config.json').write_text(json.dumps(cfg,indent=2))
(out/'README.md').write_text('''# Host 113 report-review benchmark

The implementation and benchmark changes remain on `sandbox_fork_staging`.
This harness uses dedicated service instances and `/run/skyrl-threeway-benchmark.lock`.
It does not reboot host 113, operate on host 108, or terminate unrelated workloads.

## Workloads

* Three-language startup: pinned Python 3.12-slim, Node.js and Ruby digests,
  one excluded warmup plus 50 serial samples in each supported cache/restore mode.
* Python retained creation: 256 calls at spacing 0, 10, 25, 50 and 100 ms.
  Keep all created instances until every call settles, verify liveness, then delete.
  Record actual dispatch times, client shell Ready and new-interpreter print receipt.
* Python-only live-parent HTTP fork, execution, CPU/IO, file extents, PSS growth,
  persistent save/restore and lifecycle tests. No language-specific prewarming.
* Both fork and mlink start with 64 ready reserves, eight preparation/refill workers.
  mlink has 320 total slots and 256 waiters; its native adaptive idle policy is recorded.
  Off/UFFD have 512 network ports. Cube quotas must be verified in the running service.

## Entry points

Build the live-state probe before running: `cc -O2 -static progress.c -o progress`.
The executable is a generic monotonic counter, not a prestarted language runtime.

`run_paced.py` coordinates 30 retained-creation batches. `paced256.py` saves raw
request timestamps, errors, server events and cleanup evidence. No successful-subset
last timestamp is substituted for the all-256 total. `run_refresh.py` runs the serial
startup, live-fork, Python resource and persistence suites. `finish_analysis.py`
validates and aggregates results. `report.py` renders a single Chinese-first,
English-second PDF; `rewrite_report.py` reconstructs it from the retained base
and page blocks. `paced_charts.py` draws vector completion-gap/refill charts.

Paths describe the isolated 113 deployment. Deployment scripts are not portable
installers: inspect ownership, inventories and the shared mutex before rerunning.
API key files, private keys, runtime databases and disk images are not included.

Raw evidence lives in `/home/hong/src/research/report-review-113`. Configuration
calibration cases are retained separately and are not pooled with the final cases.
The PDF describes the final measured configuration, without historical appendices.
''')
(out/'script-sha256.json').write_text(json.dumps({str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and p.name!='script-sha256.json'},indent=2))
subprocess.run(['git','-C',str(repo),'diff','--check'],check=True)
print(out)
