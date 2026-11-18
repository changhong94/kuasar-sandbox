# Six-product startup modes and current resource validation

This revision runs on the dedicated instances on host 113. Implementation and
benchmark repositories stay on `sandbox_fork_staging`. It does not modify the
108 optimization branch or merge into `sandbox_fork`.

## Measurement contract

- 2 vCPU / 2 GiB per sandbox; 64 generic slots for fork and mlink.
- Python, Node.js and Ruby use the pinned digests in `tools/config.json` and the
  commands in `tools/languages.py`. No language-specific prewarming or
  prestarted interpreter.
- One excluded warmup followed by 50 serial measurements per startup group.
- Start: before the client SDK/CLI create call or HTTP live-parent fork request.
- Ready: receipt of the random **shell** `NATIVE_...` line.
- print: receipt of the separate random **interpreter** `READY_...` line,
  including interpreter startup and output transport.
- Local warm/cold: the same final native carrier files, verified by `mincore`
  before every request. Pool readiness and file-cache residency are distinct.
  There is no global `drop_caches` operation.
- Remote: Manifest/chunk restoration with RocksDB. It does not mean a remote
  geographic network and does not require all-memory chunk hits.
- fork remote eagerly materializes the full sparse native closure inside the
  request, including verification, writes and durability barriers. It is not
  equivalent to UFFD demand paging.
- mlink, AgentENV and CubeSandbox retain default-warm reference results. Missing
  equivalent strict cold/Manifest configurations are not invented.

## Source telemetry

Payload source counters classify successful chunk Gets as memory, RocksDB file,
origin or unknown. Percentages use summed request counts or returned encoded /
encrypted payload bytes. Repeated reads count repeatedly; sparse zero/hole
ranges generate no chunk request. RocksDB file reads do not necessarily imply
physical device IO. The dedicated cache process's `read_bytes` is recorded
separately. Index/filter Block Cache hits are not payload-memory evidence.

The observation starts before create and ends after the first print command
completes, before destruction. The primary print timestamp is captured before
that after-command observation.

## Immediate refill revision

Normal fork refill has no artificial delay. Capacity includes assigned and
retiring slots; after safe durable retirement, a condition notification wakes
the worker immediately. Failed preparations retain retry backoff. The old
`E2B_TEMPLATE_POOL_REFILL_DELAY_MS` setting is no longer read. The status field
`refill_delay_ms` stays zero for compatibility.

The report presents only the final tested configuration and results. It records
actual preparation work, post-delete recovery wait and retirement-to-refill-start
scheduling latency. Internal development records are retained separately and do
not appear as a historical appendix or before/after comparison.

## Execution order

These scripts are host-specific orchestration for the existing owned deployment,
not a generic installer. Credentials remain in external private files. The
shared benchmark mutex is `/run/skyrl-threeway-benchmark.lock`; competing runs
fail rather than interfere. Destructive reset helpers assert no assigned
sandboxes and act only on the owned fork service.

1. Build/test the staging accelerator and adapter; prepare native closures and
   RocksDB services; validate real-guest Manifest restore and live fork.
2. `run_matrix.py`: startup modes, with per-case pool/cache proofs and destruction.
3. Verify the current fork adapter reports `refill_delay_ms=0`; keep all measured
   groups associated with their exact executed source hashes.
4. `continue_validation.py`: live-parent forks (50 per language), current
   execution/CPU/IO/storage/memory cases, then 50 persistent-pause/resume cases
   per product.
5. `post_validation.py`: fresh aggregation, carrier accounting, pool events,
   isolated nested-host reboot + SQLite WAL verification, disposable image
   identity audit, and 64-slot PSS partitioning.
6. `burst256.py`: retained 256-request bursts; then `verify_disk_backing.py`
   inside the owned fork network namespace verifies actual ext4/QCOW2 backing,
   independent live-parent fork writes and both destruction orders.
7. `report.py RESULTS_ROOT`: one PDF, full Chinese section followed by its
   English counterpart. It rejects incomplete or failed prerequisites.

The nested host uses two slots only for functional reboot validation; it is not
part of the formal 64-slot startup benchmark. The physical host is never rebooted.

## Resource and persistence definitions

- Short exec: eight `true` commands per round; median within each round, then
  median of five rounds. Includes RPC, process launch and return.
- CPU: guest elapsed time hashing 256 MiB; input-buffer preparation excluded.
- IO: generate, hash, write and fsync 32 MiB, not pure storage bandwidth.
- Concurrency two: eight complete create/print/hash/delete tasks per round,
  five rounds; a burst task-throughput metric, not indefinite refill throughput.
- PSS: proportionally charged resident process pages for dedicated product
  processes, including dedicated sidecars. Excludes most kernel memory and
  unmapped page cache. The zero-sandbox baseline includes common services and
  prepared slots.
- Storage: physical extent unions within each filesystem, then summed across
  filesystems. The two-sandbox write comparison uses the pre-create baseline.
- Snapshot disk increment: a different baseline, after writing the 32 MiB file
  and starting a process with 32 MiB random memory but before persistent pause.
- Save latency: persistent-pause request through API acknowledgment. Restore:
  resume/connect request through shell Ready and a newly launched Python print.
  Storage-observation wait while paused is excluded from both timers.
- Restore retains natural post-save caches; it is not claimed as a cold
  power-loss restore. PID, in-memory state, progress, file hashes and independent
  destruction are verified. Nested host resets separately verify durable
  parent/child recovery and SQLite WAL transactions.

Raw rows, code hashes, patches and service timing logs are evidence. Do not
substitute historical resource data or combine different latency distributions.

## Retained 256-request burst

After the serial and functional validation, `burst256.py` sends 256 concurrent
client create calls per product from a shared release barrier. Each created
sandbox remains alive until all requests settle; deletion never frees capacity
for unfinished requests. One disposable warmup is excluded. Create calls use a
120-second deadline and the first print command a 90-second deadline.

The report includes all-256 Ready/print time when achieved, success/failure counts,
client dispatch spread and completion-interval plots. Failed requests are not
zero-padded into completion curves. `burst_charts.py` also plots actual VM-slot
refill work for fork and mlink, distinguishing events before and after cleanup.
This is one burst per product, not 50 repeated bursts.

The burst client uses an FD soft limit of 8192 for SDK sockets and concurrent
CLI pipes; service FD limits are unchanged. Liveness is checked after all client
requests settle. Returned IDs that disappear or cannot be used are reported as
retention failures, not passing instances. Cleanup repeatedly inventories late
server publications and verifies a stable empty inventory and ready pools.
The raw burst source-version manifest records changes limited to post-timing
retention-result collection; primary create/print boundaries remain identical.
