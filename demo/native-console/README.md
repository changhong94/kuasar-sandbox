# Native Fork Lab console (108)

This deployment uses the correct `kuasar-sandbox` upstream repositories and the
`sandbox_fork_native_staging` implementation. It is separate from the legacy
console: port **18089**, `/srv/forklab-native`, `/run/forklab-native`, and
`forklab-native-*` systemd units. Port 18088 and `/srv/forklab` remain unchanged.
No benchmark service or 113 deployment is used.

The node runs two image-independent prepared slots and admits at most six
console-managed sandboxes, each with 1 vCPU, 2 GiB RAM and an 8 GiB writable
volume. The console renews each running sandbox's 24-hour lease once per hour, so it
remains available while this service is healthy. A console outage lasting an
entire lease may allow the node to expire it. Node API, proxy and
Manifest store listen only on loopback (19110–19112). The LAN console exposes
only its image/sandbox/snapshot operations, not credentials or arbitrary exec.

## Deployment

Run `deploy.py --binaries PATH` as root on 108. It refuses an existing deployment,
occupied ports or the already-allocated subnet. The binaries must be a complete
native migration build, including the guest runtime. It copies binaries instead of linking them: `node-ctl` locates sibling
executables using its own executable path.

Then import the existing immutable five demo image disks in a private mount
namespace:

```
systemd-run --unit=forklab-native-image-import \
  --property=CPUQuota=200% --property=IOWeight=10 --property=Nice=10 \
  --setenv=PATH=/srv/forklab-native/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  --setenv=GOMAXPROCS=2 \
  /usr/bin/unshare --mount --propagation private \
  /usr/bin/python3 /srv/forklab-native/app/import_images.py
```

The importer mounts the old base images read-only with journal replay disabled.
It passes their original OCI runtime configuration to the native flatten tool;
it does not copy old VM memory snapshots or modify old images. Original registry
digests and source disk hashes are recorded separately from the newly generated
native artifact digest. GNU tar lists the native trailing digest marker; Python
`tarfile` stops at an earlier sparse-stream boundary and must not be used for
that lookup. No language-specific prewarm is performed.

## Lifecycle and persistence

The console retains the established automatic names and separate image,
snapshot and running-sandbox tables. Existing saved snapshots can create new
sandboxes without being consumed. Running snapshot creation is not exposed
in this branch. Direct running-parent fork uses the authenticated
`/sandboxes/{id}/fork` API.

The console SQLite database uses WAL and synchronous FULL. A deleted snapshot
is hidden immediately; its separately published local graph is retained while
console-managed restored children still depend on it. Removing an image is not
exposed. This local demo does not implement remote-store garbage collection or
import legacy VM snapshots across different guest-runtime ABIs. Existing legacy
snapshots remain usable through the unchanged old website.

Physical host reboot semantics belong to the native persisted-snapshot path;
this console does not automatically checkpoint unsaved sandboxes at shutdown.

State, credentials, binaries, image data, screenshots and generated reports are
outside Git. Source scripts and frontend files belong in this directory.
