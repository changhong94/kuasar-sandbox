# Child network identity reset / host 113

All implementation edits remain on sandbox_fork_staging. No 108 changes.
Original workload: official python:3.12-slim digest
sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79.
64 reserves; 256 simultaneous client releases; all successful instances held
until completion and replenishment, then checked and deleted. Interpreter startup
is timed. Each formal group has one excluded warmup. No language-specific warmup.

## Diagnosis and correction

Fresh Check RPCs responded after a failed identity RPC; Exec remained rejected by
the frozen workload barrier. Initial phases localized the wait to interface
configuration. The stack-fixed-repeat4 failure captured phase 201 (link down):
netlink_sendmsg -> rtnl_setlink -> dev_change_flags -> virtnet_close ->
cancel_work_sync -> __flush_work. Evidence: probes/e2b-30ce468763ea0caf1bef4a9b.json.
This is guest driver work, not inability to connect via vsock.

Cloud Hypervisor unconditionally requested a restored-network announcement.
The Linux driver handles ANNOUNCE in config_work by calling netdev_notify_peers,
which takes RTNL. Link-down already holds RTNL and waits for config_work to finish.
The captured agent stack and upstream driver source identify this lock-order
conflict; no separate kernel-worker stack was captured.
Source references:
https://github.com/torvalds/linux/blob/v6.12/drivers/net/virtio_net.c
https://github.com/torvalds/linux/blob/v6.12/net/core/dev.c

The fix marks a rewritten fork NIC with a one-shot fork_identity_reset flag.
Both live-parent fork and Kuasar snapshot-pool clone set it. Cloud Hypervisor
restores that NIC without announcing the inherited identity. The guest still
performs complete link/address/MAC/route reset under the existing host and guest
gates. Normal migration/restore keeps announcements. Future snapshots reset the
one-shot flag to false, so this does not permanently disable announcements.
Original 15-second identity deadline, persistence and CoW remain unchanged.

A separate control-queue correctness fix schedules one queue scan when a restored
worker starts. It runs only after the device pause barrier. A saved command can
otherwise lose its old host eventfd notification. A deterministic regression
fails before and passes after this fix. This alone was NOT sufficient: the
control-scan-trial/8-repeat run retained one original timeout (255/256); its
failed results are preserved, never counted as full completion.

Temporary guest probes were used only for diagnosis, then removed. Formal runs
use the original guest root image and original Python image digest. The final
changes are in CH net.rs / fork.rs and Kuasar service/snapshot_pool.rs; existing
staging changes are preserved. No timeout increase, identity retry, artificial
completion, early deletion or gate bypass is used.

8/, 4/, 8-repeat/ are final groups; control-scan-trial/ contains the earlier,
incomplete fix. run-final.py asserts tests/builds then deploys and runs groups.
Each group retains raw request records, pool events and complete logs.
verify_disk_network.py independently checks live-parent HTTP fork, distinct guest
MAC/IP, gateway reachability, writable QCOW2/ext4 isolation, and both destruction
orders. vm.info's configured initial MAC is not a reliable assertion of the
post-ForkControl guest link MAC; the verifier checks actual guest MACs/IPs,
assigned IP records and network reachability instead.
