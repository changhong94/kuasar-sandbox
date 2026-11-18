# Fixed network-identity path: refill scaling on 113

Source: sandbox_fork_staging, unchanged from the network-reset fix.
No changes to 108. Only the owned bench-python113-fork service is reconfigured.
Each group: 64 reserves; one excluded warmup; 256 client workers released together.
Official python:3.12-slim digest:
sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79.
Timing ends when a new Python interpreter prints its random marker to the client.
All successful sandboxes stay alive until all requests finish and reserves refill.
Independent fsynced files and execution after half are destroyed are verified;
remaining instances are then deleted and absence of late instances checked.
No language-specific prewarm, deadline increase, persistence or safety change.

run.py executes 8/16/32/64 groups using the previous validated harness.
Each group retains deployment/preparation costs, complete raw requests, pool events,
load-before and phase summaries. Existing tests/build logs document the unchanged
binary provenance, not tests newly run for this configuration-only experiment.
report.py produces Chinese followed by English, completion/gap/refill curves,
and comparison.json. The maximum observed concurrent refills is calculated by
sweeping actual prepare_started/prepared intervals. It need not reach the worker
limit. P95/P99 use nearest-rank percentiles. Each configuration is one burst;
its total is not a median of repeated bursts.
restore8/ rebuilds the owned pool with its original 8-worker setting after testing.
finalize.py checks unchanged source diffs and deployed binary hashes, 1024 successes,
cleanup and final 64 reserves, then archives scripts to the staging bench checkout.
No commit, push or merge is performed.
