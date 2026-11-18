# 113: bounded parallel refill, 64 reserves / 256 concurrent Python creates

Implementation remains on `sandbox_fork_staging`; no merge, commit or push is
performed by this experiment. Host 108 and other users' processes are untouched.

- `before/`: prior 22.476802340 s batch and source/binary backup.
- `round1/`: bounded 8-worker preparation + per-record commits, 7.936209896 s.
- `results/burst256/kuasar-fork/`: final 4.982271061 s batch. Same pinned image,
  SDK command, 256-thread release and random shell Ready / Python print markers.
  Python starts after the request. One excluded warmup precedes each burst.
- All successful instances remain until all 256 finish and independent execution,
  files and the 64-reserve target are checked. Then half are deleted, survivors
  are rechecked, and the rest are deleted. No early recycling of successful VMs.
- `pool-events.jsonl` records all 256 refills with vacancy identity, start/end and
  create/device/network/stage/publish timings. No healthy-path cooldown.
- `host-all.log` contains native and RPC timings. Journald suppressed some lines;
  stage summaries explicitly report actual sample counts. These subsets must
  not be described as complete 256-request distributions. End-to-end and refill
  events are complete, independently collected files.
- `verify_disk_backing.py` and `live-fork-validation/` verify persistent
  ext4/QCOW2 isolation, live-parent process progress and both deletion orders.
- `summary.json`, `analyze.py`, and the bilingual PDF/SVG graphs retain full
  within-batch distributions. Total burst time is one observation per version.
  AgentENV 7.69 s is a prior comparable result, not a fresh run in this task.

Changes: atomic pending reservations, bounded refill workers, vacancy tracking
across out-of-order completion/failure, separate claimant/refill conditions,
per-record durable commits for single-record preparation updates, and native
pool preparation handing global serialization to the registered sandbox's own
lifecycle lock. Live-parent fork's gate, durable sync semantics and CoW remain.

Reproduction (only with the owned fork endpoint empty and shared bench mutex
available): run tests in integrations/e2b; build the native controller offline;
run `deploy.py` as root, then `prepare.py` and `burst256.py` via the owned
`py113-fork` network namespace and the python-latest-113 virtualenv. These scripts
hold `/run/skyrl-threeway-benchmark.lock` and never reset other product services.
The deployment script backs up the previous binary, so use a new result
root for a new experiment rather than overwriting these results.

Preparation is separately measured: service to 64 reserves, and image template
preparation/publication/first create without starting Python. 64 reserves are
independent of the number of running user sandboxes.
