# 64 reserves with 256 retained running sandboxes

113 only, `sandbox_fork_staging`. The ready/preparing reserve target is 64;
public or privately binding assignments do not count against that target.
Assignment commits before the refill worker can observe the vacancy. The
worker remains serial, with no normal-path cooldown. Deletion of an assigned
instance does not create another vacancy. Failed assignments are quarantined.

`burst256.py` uses the same pinned Python digest and real interpreter command
as the six-product benchmark. One excluded warmup, then 256 concurrent client
calls. The timer starts at the release barrier and ends on client receipt of
the complete random Python print marker. Client FD limit is 8192. All created
instances remain alive until requests settle. File isolation, unique network
identities, and 64 refilled reserves are checked while 256 instances remain.
Half are deleted, survivor files/execution are verified, then the remainder
are deleted. Preparation is measured separately; no interpreter prewarming.

`verify_disk_backing.py` separately validates real ext4/QCOW2-backed live-parent
fork, independent writes and both deletion orders. The existing live-parent
process-continuation test also runs twice (one warmup and one measured case,
used here as functional regression checks, not a new latency distribution).

Run host-specific preparation/benchmark commands inside `py113-fork` as root
with the existing venv. Each script holds the shared benchmark mutex. External
configuration and credential-file paths refer to the existing owned deployment;
credentials are not archived. These are not generic installation scripts.

`report.py RESULT_ROOT` creates a Chinese/English PDF and SVG charts from raw
rows. `summary.json` includes completion gaps, actual refill work, queue wait,
and initial preparation. Queue wait is not an artificial delay: the serial
worker processes preceding vacancies first. The final 64-reserve refill after
all prints is reported separately from print latency.
