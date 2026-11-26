#!/bin/bash
set -euo pipefail
export PATH=/home/hong/src/.tools/go/bin:$PATH
export GOMAXPROCS=8 GOPROXY=off
repo=/home/hong/src/research/kuasar-native-fork/kuasar-sandbox
out=/home/hong/codex-work/sevenway-fresh-181/bin
mkdir -p "$out"
cd "$repo/sandboxer"
go build -p 8 -trimpath -ldflags='-s -w' -o "$out/sandbox-ctl" ./cmd/sandbox-ctl
cd "$repo/orchestrator"
go build -p 8 -trimpath -ldflags='-s -w' -o "$out/node-ctl" ./cmd/node-ctl
for kind in runner vm-runner; do
 entry=runner_entry.go
 if [ "$kind" = vm-runner ]; then entry=vm_runner_entry.go; fi
 files=("./cmd/node-ctl/$entry")
 for name in runner_main run_sandbox taskrun prepared_vm prepared_codecs stage_catalog runner_cgroup runner_metrics launch_stages shared_controller shared_run shared_registration approved_executable shared_listener; do files+=("./cmd/node-ctl/$name.go"); done
 CGO_ENABLED=0 go build -p 8 -trimpath -ldflags='-s -w' -o "$out/node-$kind" "${files[@]}"
done

cc -O2 -Wall -Wextra -o "$out/node-run-lease" "$repo/orchestrator/cmd/node-run-lease/main.c"

cd "$repo/accelerator"
for name in cache-ctl store-ctl manifest-ctl; do CGO_LDFLAGS="-lrocksdb -lstdc++" go build -p 8 -trimpath -ldflags='-s -w' -o "$out/$name" "./cmd/$name"; done
cd "$repo/connector"
go build -p 8 -trimpath -ldflags='-s -w' -o "$out/connector-ctl" ./cmd/connector-ctl

cd "$repo/guest-runtime"
CGO_ENABLED=0 go build -p 8 -trimpath -ldflags='-s -w' -o "$out/flatten-ctl" ./cmd/flatten-ctl
CGO_ENABLED=0 go build -p 8 -trimpath -ldflags='-s -w' -o "$out/sandbox-init" ./cmd/sandbox-init
sha256sum "$out"/* > "$out/SHA256SUMS"
echo BUILD_GO_COMPLETE
