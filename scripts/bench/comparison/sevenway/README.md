# Seven-product benchmark adapters

These scripts archive the current host-specific benchmark harnesses. They are
not a generic unattended installer: configuration, credentials, immutable image
registries and existing service units are provisioned separately on the named
host. No credentials, binaries, PDF reports or measurement results belong here.

The fresh113 batch uses new result directories, 50 startup samples plus one
warmup, and 20 whole-pool preparation rounds plus one warmup. Pools contain64
ready slots and8 preparation/refill workers. Successful256-burst instances are
retained until group completion. The monitor requests human-authorized agent
checks every30minutes and stops only after audited completion and service cleanup.
Change its absolute root and session ID before reusing it elsewhere.

Record image digest, generic file-prefetch policy, selected image catalog,
private-template RAM cache preparation, persistent disk backing and code hashes.
Do not compare zero-file-prefetch and warmed templates as a code-only change.
Never preexecute the measured interpreter. Ready ends at the received shell
marker; print ends at received fresh interpreter stdout, both from client create.
User-facing product name: memlink (legacy internal identifiers remain unchanged).

Repairs must preserve completed samples and failed evidence; inspect outstanding
sandbox IDs before retrying. The main driver skips completed stages, while pool
and startup workers skip verified completed samples. Some legacy adapters need
manual partial-stage recovery; do not blindly rerun these on failure.
