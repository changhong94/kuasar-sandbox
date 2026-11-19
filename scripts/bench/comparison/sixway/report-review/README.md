# Host 113 report-review benchmark

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

## Render the reviewed bilingual report

Install `requirements.txt` in a Python virtual environment, then run:

```sh
python report.py /home/hong/src/research/report-review-113
```

The generator reads validated evidence and writes
`report/sandbox-sixway-zh-en.pdf` under that evidence directory.
PDFs, generated report manifests and rendered previews remain outside Git.
The reviewed PDF on 113 is
`/home/hong/src/research/report-review-113/report/sandbox-sixway-zh-en-reviewed.pdf`.
Chinese and English sections use the same measurements.


## Reviewed offline report (latest fork + retained five-product baseline)

`offline_report.py` is the entry point for the reviewed bilingual report. It only
reads retained evidence and renders charts/PDF; it does not start services, VMs,
or benchmarks. `report.py` remains the earlier full-cohort generator.

```sh
python offline_report.py /home/hong/src/research/sixway-full-20261119
```

The evidence directory must retain its staged `report.py` rendering definitions,
`attempts/`, `provenance/`, `deployment/`, `retirement/`, `cleanup-audit.json`,
`offline-evidence/`, `storage-supplement/` and `local108-snapshots/`. Its sibling
`report-review-113` supplies the audited five-product baseline and pool PSS;
`storage-incremental-113` supplies explicitly labelled local persistence and disk
reference batches. The generator also records the checkpoint-mode source used
for the preserved deployment. These host-specific inputs are evidence, not a
portable installer. Missing evidence fails rather than starting a new test.

Outputs stay under `<evidence>/offline-report/`: the Chinese-first/English-second
PDF, `sources.json` with input hashes, `methods.json` and `refill-audit.json`.
Generated outputs and raw measurements must not be committed.

The reviewed summary omits unmatched remote rows and the host-108 combined
save/restore row, while the body retains separate local/remote and host-labelled
results. Memory/disk labels explain baselines and sampling; reserve metrics are
recomputed from retained startup events. Refill charts deduplicate executions,
exclude preparation before the request window, separate mlink Floor/Elastic,
and split completions before/after cleanup. Charts describe completion windows,
not causation by cleanup. Cross-host comparisons are explicitly labelled.
