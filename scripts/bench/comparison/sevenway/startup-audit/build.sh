#!/bin/bash
set -euo pipefail
export PATH=/home/huawei/src/.tools/go/bin:$PATH CGO_ENABLED=0 GOMAXPROCS=2
root=/home/huawei/src/research/kuasar-native-fork/kuasar-sandbox
out=/home/huawei/codex-work/startup-latest-113/bin
for spec in sandboxer:sandbox-ctl orchestrator:node-ctl accelerator:store-ctl accelerator:manifest-ctl connector:connector-ctl; do
 repo=${spec%:*};name=${spec#*:};cd "$root/$repo"
 go build -p 2 -trimpath -ldflags='-s -w' -o "$out/$name" "./cmd/$name"
done
cd "$root/orchestrator"
for kind in runner vm-runner; do
 entry=runner_entry.go; if [ "$kind" = vm-runner ]; then entry=vm_runner_entry.go; fi
 files=("./cmd/node-ctl/$entry")
 for name in runner_main run_sandbox taskrun prepared_vm prepared_codecs stage_catalog runner_cgroup runner_metrics launch_stages shared_controller shared_run shared_registration approved_executable shared_listener; do files+=("./cmd/node-ctl/$name.go"); done
 go build -p 2 -trimpath -ldflags='-s -w' -o "$out/node-$kind" "${files[@]}"
done
sha256sum "$out"/*
