# Single-node Kuasar / CubeSandbox comparison

[中文说明](README.zh-CN.md)

These scripts test existing isolated deployments. They do not install, upgrade,
stop or clear services, and do not perform cross-node tests. Run on the Linux
deployment host with root privileges for process, journal and extent inspection.

## Reproduce

Create a Python environment in this directory:

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt

Create a config referencing existing private access files:

    sudo .venv/bin/python prepare.py config \
      --kuasar-access /path/to/kuasar/access.json \
      --cube-access /path/to/cube/access.json \
      --mount /path/to/comparison-xfs \
      --output /path/to/suite-config.json

Inspect generated paths. Defaults assume the comparison layout: kuasar/store,
kuasar/cache-rocks, cubesandbox and cubesandbox-extra. Adapt these and the
platform process/container selection in worker.py for another deployment.
Both access files must select equivalent 2-vCPU / 2-GiB Python base templates.
Never commit access files or include them in shared reports.

Retained-snapshot extent_paths and live_extent_paths are intentionally separate.
The latter must also include Kuasar's runtime directory containing writable
diffs (by default kuasar/runs). Store-only growth is not live disk-write cost.

Prepare fresh paired snapshot fixtures with full restore verification:

    STAMP=$(date +%Y%m%d_%H%M)
    sudo .venv/bin/python prepare.py fixtures \
      --config /path/to/suite-config.json \
      --output "/path/to/results/fixtures-$STAMP"

Run stages sequentially, never simultaneously:

    sudo .venv/bin/python run.py --config /path/to/suite-config.json \
      --output "/path/to/results/memory-$STAMP" --stage memory --repeats 2
    sudo .venv/bin/python run.py --config /path/to/suite-config.json \
      --output "/path/to/results/cache-$STAMP" --stage cache --repeats 3
    sudo .venv/bin/python run.py --config /path/to/suite-config.json \
      --output "/path/to/results/density-$STAMP" --stage density \
      --counts 1,2,4,8,12 --repeats 2

Regenerate JSON, CSV and SVG without rerunning workloads:

    .venv/bin/python report.py /path/to/results/cache-TIMESTAMP

Optional Matplotlib PNG/SVG figures:

    .venv/bin/pip install -r requirements-plots.txt
    .venv/bin/python plot.py /path/to/results/cache-TIMESTAMP/summary.json \
      --output /path/to/results/cache-TIMESTAMP/figure

Repeat the entropy / independent-content storage matrix:

    sudo .venv/bin/python prepare.py storage \
      --config /path/to/suite-config.json \
      --output "/path/to/results/storage-$STAMP" --instances 3 --repeats 2

    .venv/bin/python storage_report.py "/path/to/results/storage-$STAMP"

Or execute the complete single-node sequence:

    sudo .venv/bin/python reproduce.py --config /path/to/suite-config.json \
      --output-root /path/to/results --counts 1,2,4,8,12

The scripts retain snapshots, but remove their own source/restored instances
and temporary exported bundles. Fixtures update the config only after both
products pass restore checks. Output directories must be new. Failed records
are retained. Reuse --seed NUMBER for identical input bytes; use fresh seeds
for storage-growth tests to avoid deduplication with previous runs.

## Workload and timing

Each fixture contains a 64-MiB file and live 256-MiB memory buffer. Restores
check complete file/memory SHA-256 and the memory process's original UUID.
The low-entropy variant repeats a random 256-byte pattern in memory; the file
remains high entropy. Independent sandboxes still share a base template.

The density stage additionally changes one byte in every 4-KiB memory page
using different per-instance values, and writes an extra independent 64-MiB
file. It captures read-only and modified-working-set memory separately.
Repeated full-touch requests verify the modified buffer and original file.

- ready_ms: snapshot-create request until printf READY completes via E2B SDK.
- full_touch_ms: same start until memory and file hash verification finish.
- repeated_touch_ms: full verification on already-running instances.

These include hashing, SDK, command and network overhead; they are not pure VMM
restore timings. Existing API routes differ (Kuasar HTTPS, Cube HTTP); envd uses
each deployment's configured route. No overhead is subtracted.

The memory stage samples before full touch; its timings contain diagnostic
overhead and must not be compared with performance runs. Cache batches perform
a full-touch warm-up, recorded separately.

Kuasar receives explicit off/memory metadata. Memory requires one matching
prefetch-start journal message per instance. Cube retains default release
behavior: its off label does not disable all of Cube's own read-ahead.

## Metric boundaries

- Sandbox PSS includes discovered processes and descendants. Platform PSS is
  separate, including selected Cube support containers. PSS does not include
  all unmapped page cache, slab or host kernel memory.
- The current Kuasar process-PSS selection covers its release-bin processes.
  Zot, whose executable is outside that directory, is not in that PSS subtotal;
  its memory is included in the preparation service's collected cgroup totals.
  Use the raw scope and cgroup records when examining whole-deployment costs.
- Raw cgroup memory/current/stat/events, host memory and swap counters are
  saved. Never sum overlapping parent/child cgroups.
- CPU is cumulative time of sampled surviving processes. Platform deltas use
  matching PIDs. Very short-lived processes may not be captured.
- Kuasar source_read_bytes/calls are logical source reads, not physical disk
  traffic. Missing Cube counters are null, not zero. Process physical read
  bytes are a separate, layer-dependent metric.
- file-advised-cold uses POSIX_FADV_DONTNEED on experiment files only. This is
  advisory and retains application, metadata and device caches. It is NOT a
  fully cold system. No global drop_caches operation is performed.
- The outer filesystem's loop backing-file cache is also retained. Process
  read_bytes is kernel-accounted storage I/O; it does not prove SSD device reads.
- Storage uses FIEMAP physical-extent unions, counting reflink/shared ranges
  once within product paths. Compare baseline deltas. Do not treat du as
  exclusive physical bytes. Filesystem metadata, RocksDB cache and supporting
  databases are excluded; selected Cube paths also contain internal/log files.
- XFS loop on ext4 is not a native-disk performance result.
- Density covers only requested counts and this workload. Threshold fractions
  (500/1000/2000/5000/10000 ms) and sample p95 are descriptive, not a production
  SLA or proven maximum. Failed batches stop increases for that variant.
  A configurable MemAvailable floor prevents starting under memory pressure.

Preserve binary versions/hashes, machine details, seed, templates, cache
definition, concurrency and failures with published charts. Do not stop
unrelated workloads on a shared host.
