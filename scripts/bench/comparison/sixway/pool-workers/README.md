# Refill concurrency comparison on host 113

Each group keeps 64 reserves and issues one simultaneous 256-request Python
burst after one excluded warmup. Same pinned python:3.12-slim, command, SDK and
release-to-random-print timing. The Python interpreter starts inside the timed
request. Successful instances remain until completion and validation, then half
are deleted, survivors verified, and the remainder deleted.

Groups execute in order 8, 16, 32, 64. An additional independent 8-repeat follows
because the first baseline exposed guest network-reset RPC timeouts. No failure
is hidden or replaced by a retest. all_print_s is null unless all 256 succeed;
last_success_s excludes failed calls; all_requests_settled_s includes timeouts.
All groups retain complete client results and 256 refill telemetry records.
Journald may rate-limit detailed host logs, so no claim of complete native logs.

Only the permitted worker upper bound changes from 32 to 64. The default remains
8. Capacity reservations may prevent all 64 worker threads from simultaneously
preparing slots. peak_inflight reports actual overlap. Persistence, safety gates
and CoW are unchanged; host 108 and other users' processes are untouched.

run.py --groups 8 16 32 64 runs the sequence. Use a fresh root for a new run:
per-group benchmark output must not exist. Each deployment/benchmark acquires
the shared host bench mutex and rejects a nonempty owned endpoint. Deployment
resets only bench-python113-fork. run.py continues partial-success batches only
if cleanup and independent-instance verification passed. summarize.py records
both successes and errors; report.py creates Chinese then English PDF content.
Do not interpret one burst per group as a statistically established optimum.

Code and benchmark archive remain on sandbox_fork_staging, unmerged/unpushed.
