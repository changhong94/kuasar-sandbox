#!/bin/bash
set -euo pipefail
M=/home/huawei/src/research/sixway_startup_108
[[ $EUID == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
mountpoint -q "$M/data" || { echo 'Benchmark XFS is not mounted. Run scripts/prepare-storage.sh first.' >&2; exit 1; }
for unit in bench108-off-serve bench108-uffd-serve bench108-agentenv bench108-mlink bench108-fork cube-sandbox-cube-api cube-sandbox-cube-proxy;do
 systemctl is-active --quiet "$unit" || { echo "Not ready: $unit" >&2; exit 1; }
done
out="$M/results/startup-matched-10-$(date -u +%Y%m%dT%H%M%SZ)"
"$M/venv/bin/python" "$M/scripts/startup-matched.py" "$M/deploy/startup.json" --out "$out"
cat "$out/summary.json"
