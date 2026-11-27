# Native fork migration smoke tests

`source-lock.json` records the six correct `kuasar-sandbox` upstream bases.
Each checkout is separate from the legacy deployment. Branch name:
`sandbox_fork_native_staging`. `workspace.sh` creates the sibling Go workspace
without altering upstream module files. It refuses to overwrite a workspace.

Build the unmodified bases first with the umbrella `make build`. Save its
binaries, kernel and runtime bundle in a distinct `baseline-bin` directory.
Then build the development sandboxer and guest runtime into `fork-bin`.
Do not replace a running service's artifacts. The guest runtime bundle must
contain the matching fork-aware init. See `sandboxer/docs/native-fork.md` for
implemented scope and migration gaps.

The smoke harness requires Linux KVM, root, Docker, iproute2, e2fsprogs, and these
binaries in `--bin`: sandbox-ctl, cloud-hypervisor, vmlinux,
sandbox-runtime.bundle, flatten-ctl, store-ctl. Use a pinned image already present
in Docker. `--work` must not exist. All evidence and artifacts stay there, outside
Git. Remote tests generate a private mode-0600 manifest key; never commit it.

```sh
sudo python3 smoke.py --bin /isolated/baseline-bin --work /evidence/baseline-local \
  --image python@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
# Add --remote for a separate original Manifest/chunk restore test.
# For the development binaries add --fork. Add --child-first to reverse teardown.
```

`--remote` starts a task-owned loopback store (CDC, AES chunk/manifest encryption,
filesystem backend, no cache). It does not use a production storage service.
`--network` must run in a **new private host network namespace**:

```sh
sudo bash -c '
set -e
ns=native-fork-smoke
ip netns add "$ns"
trap '\''ip netns del "$ns"'\'' EXIT
ip -n "$ns" link set lo up
ip netns exec "$ns" python3 /absolute/path/smoke.py --fork --network \
  --bin /isolated/fork-bin --work /evidence/fork-network \
  --image python@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
'
```

Network mode creates only namespace-local TAPs, keeps the child link down until
Ready, verifies MAC/IP/hostname and fresh UDP messages from both guests. It is
for the migrated fork path, not an upstream restore claim. The workload retains
its Python PID, random identity and counter across capture; file writes diverge;
after deleting either VM the other continues running. Test memory is 512 MiB
per guest and one vCPU, at most two VMs. This is a correctness smoke test, not the
six-way benchmark or a cold-cache/performance comparison. Timings include an
interpreter only for the separate verification execs, not in fork Ready.

No global cache drops, sysctl changes, process-name kills, service restarts or
existing sandbox deletion are used. Only subprocesses created by this test are
terminated. Runtime roots are unique `/run/kn-*` directories. Do not commit
results, guest disks, images, credentials or generated PDFs.

Add `--reject-sockets` to `--fork --network` to verify the first-stage boundary:
a TCP listener explicitly bound to the parent IP fails before child Ready, while
the source keeps running. The committed capture is retained.

Use `--tcp-state` with `--fork --network` to retain a real parent TCP connection
through capture. The application handles the child's inherited-socket error by
reconnecting. The host checks that the parent has exactly one connection with
its original token, while the child obtains a distinct token and source IP.
The same workload retains a wildcard TCP listener and wildcard UDP socket;
both guests accept fresh traffic on their inherited ports without cross-delivery.
Local and remote runs use opposite destruction orders. Random output is checked
for divergence; this is not a cryptographic randomness-quality test.

## Native connector and API

Add `--tapfd` to `smoke.py --fork --network` to use the real connector provider
and automatic child gate. `--tcp-state` additionally keeps a guest-internal
loopback connection exchanging bytes; both copies must continue alongside the
parent's unchanged external connection and the child's newly opened connection.
The patched CH, fork-aware guest bundle and matching host binary are all needed.

`api_smoke.py` creates a separate conductor, Proxy, store and four-port vswitch.
It uses a unique systemd runner template with no idle VM pool, a private network
namespace, loopback-only service listeners and unique run/data roots. It does not
modify global forwarding or restart existing services. It temporarily owns the
host route `100.123.120.0/24`; run one instance at a time and ensure that subnet is
unused. Its `--image-file` must be a native flattened tarstream from the pinned
smoke image. It exercises two generations, inherited process state, independent
writes, parent-first deletion, and reclamation of temporary capture carriers.

```sh
sudo python3 api_smoke.py --bin /isolated/fork-bin \
  --work /evidence/native-api-local --image-file /evidence/baseline/root.image
# Add --remote for Manifest publication and lazy restoration.
# Add --sdk-python /isolated/venv/bin/python for E2B SDK fork, exec and file APIs.
```

The API harness additionally needs node-ctl, connector-ctl, e2b-key-ctl and
manifest-ctl. SDK checks use E2B 2.64.0, an ordinary `python:3.12-slim` filesystem,
root user and explicit `/` cwd (this image has no `/home/user`). Keys pass only
through private files, environment and stdin. A wrong parent token must be
rejected when addressing the child through the Proxy. `fork_api_ms` in SDK mode
also includes launching the test's host-side SDK helper and connecting to the
parent; it is not a pure server or Python-print benchmark.


## Running fork and generic pool checks

Use `api_smoke.py --memory-stress --fork-rounds 10` for ten captures from one
running source while a 16 MiB workload verifies page contents; the final child
also forks after the original parent is deleted. Run once locally and once with
`--remote`. `runners.log` contains task-specific capture phases. These correctness timings are not a six-way performance benchmark.
The recorded CH-pause-through-reattach interval excludes guest quiesce preparation.

`smoke.py --checkpoints --fork --remote --network --tcp-state --tapfd`
exercises direct Manifest capture while the source has live external and loopback
connections; it does not first serialize through the API's local publication stage.

The opt-in Go `TestKVMGenericPoolTwoImages` needs SANDBOX_POOL_IMAGE_ONE and
SANDBOX_POOL_IMAGE_TWO (prepared placeholder configs for Python and BusyBox),
SANDBOX_SDK_KVM_CH and SANDBOX_POOL_CTL. Both VM slots are ready before image
assignment. The test verifies different root-image geometries, immediate reserve
refill, continued ownership after pool close, running fork, disk isolation and
independent destruction. No existing service supplies these slots.

The current API harness also verifies SQLite WAL transactions with
`synchronous=FULL`. Checkpoint-enabled runtime disks opt into durable guest FLUSH;
local capture/publish success includes explicit file and directory sync. The
`parent_route_resumed_before_capture_commit` field verifies that the guest resume
notification restores the parent's Proxy route before persistence completes.
A successful read/restore test does not by itself establish host power-cut safety.

Build the matching platform through the normal umbrella `make build`, with
`GOWORK` pointing to the sibling workspace. The CH recipe fingerprints source,
patch and compiler inputs; existing binaries without matching input stamps are
rebuilt. Keep the assembled `bin/<arch>` isolated from the legacy deployment.

The same opt-in fixture variables also enable `TestKVMPreparedRunAdapter` and
`TestKVMPreparedRunnerTransport`. The latter requires a newly built sandbox-ctl
containing `prepare-run`; it uses inherited private pipes to boot a generic VM
before selecting the different BusyBox image. Run the runtime test binary as
root for KVM/UFFD. Use `api_smoke.py --prepared-pool` to exercise ordinary HTTP Create with two
image-independent prepared slots and a separate ordinary restore runner pool.
`--pool-image-two <root.image>` additionally claims the same pool with a different
image; `--remote` exercises Manifest publication. The test covers exported
Sandbox template creation, live fork, SQLite FULL transactions, dirty memory,
credential/file isolation and independent deletion. Python executes through the
real E2B SDK. Minimal BusyBox executes through the native command API because
the upstream E2B profile requires image tools including `/usr/bin/ionice`; this
is not presented as minimal BusyBox E2B command compatibility. No interpreter is
started during preparation. These are correctness checks, not latency benchmarks.

`--restart-controller` restarts only the isolated conductor while its VM runners,
proxy and storage stay alive. It verifies the source guest process keeps its PID
and identity, continues advancing its counter, retains SQLite state, and supports
subsequent pooled creation, fork and independent deletion. This is controller
recovery coverage, not a host reboot or power-cut test.

## Direct inherited-RAM migration

`private_native_smoke.py` exercises `sandbox-ctl run --private-ram-fork` and
`fork --backend native-private` using separate source/child owner processes.
It requires the isolated migrated Cloud Hypervisor (v54.1 lineage), not the
v51 snapshot-backed binary. The guest kernel/runtime bundle remains the native
Kuasar build. Supply the same pinned Python
configuration used by the native tests:

```sh
sudo python3 private_native_smoke.py \
  --cli /isolated/sandbox-ctl-private --ch /isolated/native-cloud-hypervisor \
  --config /evidence/python.json --work /evidence/private-fork --count 10
```

The fixture starts a live Python counter before fork, checks its inherited PID
and continued progress, checks SQLite FULL transactions and disk divergence,
terminates the entire parent owner, forks a second generation, and destroys the
grandchild before its source. Every successful sample requires all checks.
Cleanup targets only subprocesses created by the harness.

The request clock starts before spawning the fork CLI. `request_to_child_ready_ms`
ends at the child's readiness event; `request_to_complete_ms` also waits for the
source reattachment/completion record; `request_to_print_ms` then includes a new
Python interpreter and reception of a random print marker. No language prewarm
is performed. Durable disk checkpoint materialization is included. This is a
functional development-path measurement, not the old six-way production bench.

For direct page-sharing evidence, run the opt-in Go
`TestKVMNativePrivateRAMLaunch` with `CH_FORK_ACCOUNT_PSS=1` and
`CH_FORK_VERIFY_PAGES=1`; its input variables are `NATIVE_PRIVATE_CONFIG`,
`NATIVE_PRIVATE_CH`, and `NATIVE_PRIVATE_CTL`. It verifies shared physical pages
before either VM resumes. The earlier C-init VMM fixture is a separate lower-level
test, not a substitute for these native guest/owner lifecycle tests.

Scope and deliberate capability rejections are listed in
`sandboxer/docs/native-fork.md`. `api_smoke.py --native-private` selects the isolated conductor's direct-RAM
HTTP/E2B backend. `--prepared-pool --pool-image-two PATH` checks one image-free
pool with different images; `--pause-resume` checks process-preserving save and
restore. Add `--remote`
for encrypted chunked Manifest storage. These tests do not switch the legacy
website. The SDK fixture starts a separate SDK client process for each action;
its outer timings include that process/import cost and must not be substituted
for a persistent-client SDK benchmark. Direct CLI and HTTP timings are reported
separately.


### Dynamic budgets and inherited UDP

`api_smoke.py --native-private --dynamic-memory --connected-udp --pause-resume
--fork-rounds 10` uses a real isolated resource controller, a 512 MiB capacity,
384 MiB startup budget and a balloon. Each child has a separate reservation.
The connected UDP process is inherited without restarting it; the host echo
server must observe distinct parent/child source addresses, including a second
generation after snapshot restore and source deletion. Snapshot restoration
binds the currently allocated provider TAP even when it is a reconnect rather
than a clone. The historical TAP in the snapshot is never an allocation lease.

Add `--memory-stress --restart-controller` (one fork round)
to test ongoing memory writes, running fork and controller restart; add
`--remote` for encrypted chunked Manifest publication and demand restore.
These are correctness scenarios; controller restart is separate from host reset.

### Isolated nested host reset

`build_nested_host.py --workspace WORKSPACE --output NEW_DIRECTORY` constructs
an isolated Linux host disk from the current isolated binaries, host kernel,
static BusyBox and Python standard library. Run as root, then execute
`run_nested_reboot.py --ch WORKSPACE/cloud-hypervisor/target/debug/cloud-hypervisor
--work NEW_DIRECTORY`. It uses two vCPUs and 4 GiB for an outer VM with nested
KVM. It never reboots the physical machine or kills processes it did not spawn.

Inside that host, a running parent and direct-RAM child preserve an inherited
Python process and commit different SQLite FULL values. Both are snapshotted
to local artifacts and encrypted Manifest chunks. After all four publications
complete, the test kills its outer VMM without shutting down its guests, then
boots the same disk. Both modes must restore the original processes, committed
values, independent writes and independent deletion. The test covers abrupt
nested-host loss and restore from the last durable checkpoint; it is not a
physical-device power-loss test or a claim that unsaved RAM survives reboot.
