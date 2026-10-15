# Kuasar benchmark setup

[简体中文](README.zh-CN.md)

This directory contains benchmark scripts, dependency preparation, source builds,
deployment, cleanup, and internal timing patches.

## Scope and working directory

Run the following command from the root of this repository. All subsequent commands
assume that you remain in `scripts/bench`:

```bash
cd scripts/bench
```

The lifecycle scripts currently target the existing Alice deployment. Some scripts
still contain machine-specific paths, service names, network settings, and a base
image ID. Review `bench_lifecycle.py`, `deploy-source.sh`, `prepare-node.py`,
`prepare-storage.py`, and `run-bench.py` before using another machine. Relative
commands in this document do not make those scripts portable.

The source layout separates the six official repositories from this fork:

```text
<source-directory>/
  kuasar-sandbox/
    kuasar-sandbox/
    accelerator/
    connector/
    guest-runtime/
    orchestrator/
    sandboxer/
  <fork-owner>/kuasar-sandbox/scripts/bench/
  .tools/
  .deployment/
```

Below, `.deployment` and `.tools` refer to directories under the source directory,
not under this repository. Private deployment state and results stay outside Git.

## Prepare dependencies, build, and deploy

```bash
python3 prepare-bench.py --check       # Inspect dependencies only
python3 prepare-bench.py               # Dependencies -> patches -> build -> deploy
python3 prepare-bench.py --deps-only    # Dependencies only
python3 prepare-bench.py --build-only   # Dependencies, patches, and build only
```

The default command waits for deployment readiness; it does not run benchmarks.
A healthy deployment is reused only when its timing-patch build receipt matches.
An existing unpatched, incomplete, or unhealthy deployment is not overwritten:
inspect it, or run `clear-bench.py` before preparing it again.

Dependency preparation installs only missing apt packages and pinned Python packages
from `requirements.lock.txt`. It does not upgrade existing packages. Conflicting
Python versions or an apt plan that upgrades/removes installed packages cause it to
stop. When dependencies are present, it skips apt update/install and pip install.
Initial package installation still runs distribution package hooks.

Python packages use a dedicated `.deployment/bench-venv`. The dependency installer
resolves the invoking user's home even under sudo. `--venv` selects another environment
with `--deps-only` or `--check`; full deployment uses its configured environment.
Go, Rust, Docker, and KVM are checked, not installed or configured automatically.
System package repair and machine-specific filesystem repair are outside its scope.

## Build and deployment helpers

```bash
bash build-official.sh
bash deploy-source.sh
sudo journalctl -u kuasar-hong-node -f
```

These are lower-level helpers; prefer `prepare-bench.py` for the complete workflow.
The build helper uses the local `.tools` toolchains and dependency caches, defaults
to four build jobs, and records source revisions/toolchain versions in
`.deployment/build-versions.txt`. It does not update source or manage timing patches.

Deployment creates an isolated Store, Cache, Registry, switch, Conductor/Proxy, and
Python snapshot template. It refuses to overwrite existing service definitions.
The readiness marker is `KUASAR_HONG_NODE_READY`. The current HTTPS listeners are
`127.0.0.1:443` for control and `127.0.0.2:443` for data.

Access configuration is saved in `.deployment/access.json` with root-only permissions
(0600). Restarting the node service creates a new run directory and test template.

## Run a benchmark

Use the dedicated virtual environment's Python, not the system Python. For the
current source layout, set the interpreter once and run:

```bash
BENCH_PYTHON="$HOME/src/.deployment/bench-venv/bin/python"
sudo "$BENCH_PYTHON" run-bench.py --prefetch memory --warmup 2 --samples 10
```

Change `memory` to `off` for a run without memory prefetch. Runs are sequential.
Each round creates a sandbox, executes `echo BENCH_OK; python3 --version` twice,
then deletes the sandbox and checks that its API returns 404. The wrapper calls
`bench.py`'s `run_round` and replaces its direct directory cleanup with API checks.

Results are written to `.deployment/bench-smoke-YYYYMMDD_HHMMSS/`:

- `samples_*.jsonl`: per-round records, including warmups and available timing data.
- `samples_*.csv`: selected per-round metrics.
- `summary_*.json`: formal sample count and E2E minimum, median, and maximum.

Internal timing requires the patched build. Without `launchTiming`/`launchMs`, only
observable client metrics are recorded. This wrapper does not produce the original
OpenClaw workload or a full stage-by-stage P95 report. Align probes, sample counts,
cache state, and host load before comparing performance.

The deployment user can browse reports. `local.env` remains root-only because it
contains credentials. Never commit access configuration, environment credentials,
TLS private keys, or runtime directories. `e2b-env.sh` is a legacy example with empty
credentials; the wrapper uses its generated private environment file.

## Clear the environment

```bash
python3 clear-bench.py --dry-run
python3 clear-bench.py                    # Deployment, builds, and timing patches
python3 clear-bench.py --deployment-only  # Keep builds and source patches
python3 clear-bench.py --build-only       # Refuses a live deployment
```

Deployment cleanup removes this environment's sandboxes, snapshots, Store/Cache/Registry
data, two `kuasar-hong` services, and generated access configuration. It first runs the
owned deployment's teardown to release its networks and dynamic services. Ownership
mismatches or incomplete teardown stop cleanup and preserve diagnostic state.
Other users' Kuasar deployments, system dependencies, and shared Docker images are retained.

Build cleanup runs the five components' `make clean` targets and removes aggregate
build outputs, preserving `build/tarball/` downloads and checksum files. It also retains
native dependency source/download caches, `.tools`, the Python environment, historical
benchmark results, and unrelated source edits. Run `prepare-bench.py` to rebuild afterward.

## Timing patches

Preparation preflights both orchestrator and sandboxer patches before applying either.
A successful reverse check identifies an already-applied patch and skips it. A clean
forward check allows application. Partial applications or conflicting changes stop
preparation without resetting source files.

Adapted patches live in `patches/`; earlier versions are compatibility candidates.
Comments marked `Timing patch adaptation:` explain changes for the current
`AssignWithFence` and `RuntimeSpec` flows. Successful build verification saves
`.deployment/timing-build.json` for subsequent reuse checks.

Default cleanup and `--build-only` reverse the patches after cleaning build outputs;
already-removed patches are skipped. `--deployment-only` leaves patches in place.
Reverse applicability is checked before teardown, and unrelated source edits are retained.
Patch management does not change Git HEAD or create commits.
