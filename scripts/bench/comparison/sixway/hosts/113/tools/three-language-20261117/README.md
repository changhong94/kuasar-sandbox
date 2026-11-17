# 113 three-language six-product startup run

This directory preserves the host-specific preparation and execution scripts used
for the 2026-11-17 Python / Node.js / Ruby run on `hong@10.213.17.113`.
Shared collectors, language definitions, identity checks and statistical validation
are versioned in `sixway/aligned/`; they were unchanged during this run.
**No PDF generator, PDF, performance report or measured-result files are included.**

## Protocol and observed validation

- Each language uses one fixed amd64 OCI manifest digest across all six products.
  `config.json` records the actual template IDs and credential **file paths**, not
  credential contents. IDs are deployment state, not portable defaults.
- 2 vCPU / 2048 MiB; fork and mlink ready pools have capacity 2.
- Each of 18 groups has one disposable warmup and 50 serial measured requests;
  product order rotates. All 900 measured requests and 18 warmups completed on
  their first attempt in the recorded run. No failed sample replacement.
- Measure immediately before SDK/CLI create through client receipt of the random
  interpreter print line, including fresh interpreter startup. The shell marker
  is only a separate diagnostic event. No language-specific interpreter training.
- Fork retains bounded generic file caching (512 MiB per image); this is not a
  cold-cache benchmark. Preparation and post-delete refill wait are separate.
- Each product/language also verifies two sandboxes with different file contents:
  destroy each order, execute a fresh interpreter in the survivor, then clean up.
- `final-audit.py` checks sample counts, first-attempt success, cleanup ledgers,
  isolation results, and final native inventories. Reusable pool slots remain.

## Host-specific layout and dependencies

Scripts use `/home/hong/src/research/sixway-languages-20261117` as the work root.
Place the shared `sixway/aligned/` scripts in its `tools/`, then overlay this
directory's Python files and `config.json`. Create `results/`, `assets/` and
`backups/` first. Use `/home/hong/deploy/comparison/venv/bin/python` for SDK
operations, with root/namespace access. Exact commands are recorded in each
script; the six services, registries, certificates and credentials must already
exist. Review host paths and service ownership before executing on another host.

The scripts assume the 113 namespace layout (`bench113`, `bench113-u`,
`bench113-m-generic`, `py113-fork`) and the existing guest registry forwarding.
Node/Ruby `assets/<language>/` must contain `image.json`, `root.ext4` and the
pinned OCI input; fork runtime and rebuilt binaries are separate inputs, not
tracked here. `deploy-fork.py` also needs the previous aligned run's
`tools/reset-fork.py`, which refuses assigned sandboxes before draining its pool.
Deployment helpers are **not** a generic installer or safe concurrent-job runner.

## Preparation sequence and recovery evidence

1. Check native inventories in each product namespace with `inventory-before.py`.
   Publish the pinned OCI inputs to the existing benchmark registries. Run
   `image-provenance.py` inside the registry namespace to verify manifest/config
   SHA256 and architecture. It does not download or execute an interpreter.
2. Run `prepare-sdk.py PRODUCT LANGUAGE` for off/UFFD in their own namespaces.
   Run `prepare-native.py PRODUCT LANGUAGE` for AgentENV/Cube in `bench113`.
   Builders use native sleep; Cube waits for actual build completion.
3. Run `deploy-fork.py` in `py113-fork` after reviewing its fixed paths. It backs
   up owned deployment files, drains only the owned pool, installs binaries and
   prepares the three image templates in the shared pool. It changes only
   `bench-python113-fork` and its service drop-in.
4. mlink helpers preserve the actual preparation/recovery sequence, including
   failed attempts: `prepare-mlink.py` changes the owned service from 64 to 2
   slots and imports templates. **Do not treat this historical helper as a
   successful all-language one-shot installer:** its successive prewarm requests
   exceed the total storage budget of 2. `finish-mlink.py` resumes from the saved
   Python/Node template records, disables the previous policy, imports missing
   Ruby, and prepares/disables each policy in turn. Old persisted 64-slot
   overrides must be disabled via mlink's management API before the 2-slot restart.
   Run these in `bench113-m-generic`, with no assigned sandboxes. Neither helper
   should be rerun blindly against an active test deployment.
5. Fill all 18 template IDs in `config.json` from successful template records;
   fork maps Python/Node/Ruby to `base`/`node`/`ruby`. Preserve the pinned digests.
   `phase.py LABEL COMMAND...` captures preparation elapsed time, exit status and
   complete logs, including failures.

## Formal run and cleanup verification

Run `run-matrix.py` with the SDK virtualenv and namespace privileges. It requires
`results/matrix` not to exist, performs policy switching and identity preflight
under `/run/skyrl-threeway-benchmark.lock`, then invokes the shared startup
collector (which takes the same lock), summarizes each language, and validates
both destruction orders. `switch-language.py` enables only the selected mlink
image's two storage slots; this cost is recorded outside request timing.

After all three languages finish, run `final-audit.py`. Preserve failures and
partial outputs; do not delete them and rerun to obtain a preferred distribution.
Native inventory scripts assert no assigned test sandboxes; they do not kill
unknown instances. Do not stop other users' services or drop global caches.

The actual run's data lives at the above work root on 113, with a local copy in
`/home/huawei/codex-work/sixway-languages-113/results`. PDF/report generation is
intentionally outside this commit and remains under revision.
