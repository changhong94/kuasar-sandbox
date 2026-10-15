#!/usr/bin/env bash
set -euo pipefail
ROOT="${KUASAR_SOURCE_ROOT:-$HOME/src/kuasar-sandbox}"
TOOLS="${KUASAR_TOOLS_ROOT:-$HOME/src/.tools}"
STATE="${KUASAR_STATE_ROOT:-$HOME/src/.deployment}"
export PATH="$TOOLS/go/bin:$TOOLS/rust/bin:$PATH"
export GOMODCACHE="$TOOLS/gomodcache" CARGO_HOME="$TOOLS/cargo"
export https_proxy="${https_proxy:-http://127.0.0.1:3128}" http_proxy="${http_proxy:-http://127.0.0.1:3128}"
export no_proxy=localhost,127.0.0.1,10.213.17.53,.huawei.com
export KUASAR_BUILD_JOBS=4 GOMAXPROCS=4 CARGO_BUILD_JOBS=4 GOFLAGS=-p=4
mkdir -p "$STATE/logs"
{
 date -Is
 go version
 rustc --version
 for r in kuasar-sandbox accelerator connector sandboxer guest-runtime orchestrator; do
  printf '%s ' "$r";git -C "$ROOT/$r" rev-parse HEAD
 done
} > "$STATE/build-versions.txt"
make -C "$ROOT/kuasar-sandbox" build e2e-zot
