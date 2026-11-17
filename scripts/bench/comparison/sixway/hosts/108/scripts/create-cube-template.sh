#!/bin/bash
set -euo pipefail
cd /opt/bench108/import113/comparison
test -r /sys/kernel/btf/vmlinux
systemctl is-active --quiet cube-sandbox-cubelet
curl --noproxy '*' -fsS http://127.0.0.1:15001/v2/comparison/python/manifests/local >/dev/null
echo '2ec92f920e1c2bf1907f5556b239541b9bf0ee327d9772d15559c8eec019d979  assets/cube-envd' |sha256sum -c -
/usr/local/bin/cubemastercli --address 127.0.0.1 --timeout 15m tpl create-from-image --image http://127.0.0.1:15001/comparison/python:local --alias comparison-python --writable-layer-size 1G --expose-port 49983 --expose-port 8080 --probe 49983 --probe-path /health --enable-inject-envd --envd-path "$PWD/assets/cube-envd" --cpu 1000 --memory 2048 --cmd /bin/sh --arg=-c --arg='id user >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash user; exec python3 -m http.server 8080' --json
