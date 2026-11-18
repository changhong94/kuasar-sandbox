# 113 startup modes and live-parent fork

This suite extends the six-product, three-language startup workload. It uses
the pinned image digests and exact commands in the existing `languages.py`.
The request-to-shell marker is **Ready**; request-to-interpreter output is
**print**. API return is a third, earlier event. Never label print as Ready.

Each formal group has one disposable warmup followed by **10 serial samples**.
P95/P99 use nearest rank and therefore equal the maximum for n=10. Every
successful sample must be destroyed. Do not discard latency outliers.

## Supported conditions

- `local_warm`: native local S/E/image carriers, verified resident with mincore.
- `local_cold`: the same carriers, targeted fsync/fadvise(DONTNEED) and mincore
  zero-residency verification **before each request**, including after warmup.
- `remote`: original Manifest/chunk references, independent Redis memory tier
  over UDS, persistent authoritative Store retained. Require cache hits > 0,
  origin fetch delta = 0 and cache/Redis disk read_bytes delta = 0.
- `product_default_warm`: explicitly separate reference result for products
  whose private cache/pooled block-device state is not covered by the strict
  native-file conditioning protocol. Do not relabel this as verified cold.
- `live_parent_fork`: POST `/sandboxes/{parent_id}/fork` with `count=1`, followed
  by `Sandbox.connect()`. Installed E2B SDK 2.25.1 has no `Sandbox.fork()` method.

Native off/UFFD preparation must materialize the immutable image dependency as
well as the snapshot and writable layer. `publish --reduce-ref any` alone left
an immutable Manifest image reference in this deployment. `complete_native.py`
converts it and uses verified `--replace-ref` publication. It never uses
`--skip-verify-ref`. The final resolved configuration must have no Manifest refs.

## Owned deployment and safety

Current working artifacts live at `/home/hong/src/research/startup-modes-113`;
the scripts use the existing sixway config at
`/home/hong/src/research/ready-regression-113/tools/config.json`.
Run with root privileges in the configured product network namespace. Prefer
`nsenter --net=/run/netns/...`: `ip netns exec` also creates a mount namespace
which can hide the existing BPF pins from a replacement conductor.

All mutating/measurement phases take `/run/skyrl-threeway-benchmark.lock`.
`STARTUP_MODE_LOCK_HELD=1` is reserved for children of the lock-owning coordinator.
Never run global drop_caches, resize another user's pools, or kill unrelated VMs.

Changes to Kuasar/CH belong to `sandbox_fork_staging`; this suite does not merge
or push `sandbox_fork` and never modifies the 108 host.

## Workflow

1. Build the static `progress.c` probe and standard-library `unseal.go` helper.
   The latter reads an owned, single-tenant benchmark registry record through
   stdin and returns its key only to a captured subprocess pipe. Never invoke
   it interactively or save/print the resulting key.
2. `prepare_native.py kuasar-off` and `prepare_native.py kuasar-uffd` publish
   the pinned snapshots. `complete_native.py` materializes immutable images;
   run it with the common lock held and no active benchmark samples. Preserve
   original publication records as preparation evidence.
3. Configure the owned conductors' `checkpoint.remote.ref_location_parent`
   to `file:///home/hong/src/research/startup-modes-113/native` and validate
   configuration. `reload_conductor.py` is invoked through an owned service's
   ExecReload so the replacement stays inside its cgroup. It refuses reload
   while the node has any sandbox records. Keep root-only config backups.
4. Compile the CH staging change that adds CLOCK_MONOTONIC `mono_ns` to
   `VM_FORK stage` events. `deploy_trace.py` archives the old binary and resets
   only the owned fork pool, after verifying that no assigned sandbox exists.
5. `run_matrix.py` runs native warm/cold groups and default-path references.
   The initial RocksDB remote batch is diagnostic: origin=0 alone does **not**
   prove in-memory chunks because BlobDB reads can still occur.
6. `prepare_memory.py` starts only the named `bench-startup-modes-redis` container
   and `bench-startup-modes-cache-{off,uffd}` services. It uses an already present
   pinned Redis image, a private Unix socket, no RDB/AOF for the disposable cache,
   and unchanged persistent Store origins. It fills complete source closures.
   `run_memory.py` archives the RocksDB batch and measures memory-backed remote.
7. `live_fork.py --samples 10 --out ...` runs inside `py113-fork`. The source
   runs a native in-memory counter before fork. Each sample verifies inherited
   PID/counter state, progress in both branches, independent files, and both
   destruction orders. No interpreter is started in the source preparation.
8. `final_audit.py` validates all formal evidence. `analyze_live.py` correlates
   actual request/CH timestamps. `report.py` generates the Chinese PDF and SVGs.

The live timelines use a real sample nearest the end-to-end median and the
maximum sample. Parent/child/API/persistence intervals may overlap. Never
construct a timeline by summing phase medians. Uninstrumented connection/identity
subintervals remain explicitly grouped, not estimated as individual spans.

## Artifacts and cleanup

Keep public results, source hashes, patches, cache proofs, preparation costs and
the report together. Do **not** include `backups/*conductor.yaml`, API key files,
private registry rows or other secret-bearing deployment files in report bundles.

After measurement, restore both original manifest cache endpoint files before
stopping the two owned memory-cache services and removing only the named Redis
container. Retain native artifact locations for reproducing native modes.
Idle generic pool slots are not leaked benchmark sandboxes; verify assigned=0.

Full matrix coverage is deliberately explicit: fork has verified native cold/warm
and live fork; off/UFFD have verified native cold/warm and Manifest memory mode.
mlink/AgentENV/Cube default references do not claim all three strict modes are
supported or measured. This limitation must remain visible in the report.
