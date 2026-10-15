#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/hong/src/kuasar-sandbox/kuasar-sandbox
STATE=/home/hong/src/.deployment
FORK=/home/hong/src/changhong94/kuasar-sandbox
BIN="$ROOT/bin/x86_64"
DATA=/var/lib/kuasar-hong-demo
PY="$STATE/bench-venv/bin/python"
if sudo systemctl cat kuasar-hong-node.service >/dev/null 2>&1; then
    echo "kuasar-hong-node.service already exists; inspect it before redeploying" >&2
    exit 1
fi
python3 "$FORK/scripts/bench/prepare-storage.py"
python3 "$FORK/scripts/bench/prepare-node.py"
bash -n "$STATE/serve-hong-node.sh"
unit=$(mktemp)
trap 'rm -f "$unit"' EXIT
cat > "$unit" <<EOF
[Unit]
Description=Hong isolated Kuasar source deployment
After=network-online.target kuasar-hong-prep.service
Requires=kuasar-hong-prep.service
[Service]
Type=simple
User=root
Environment=DEMO_DATA_DIR=$DATA
Environment=DEMO_QUICKSTART=1
Environment=DEMO_KEEP=1
Environment=DOMAIN=sandboxes.hong.local
Environment=BIN=$BIN
Environment=PYTHON_BIN=$PY
Environment=PATH=$BIN:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/bin/bash $STATE/serve-hong-node.sh
KillMode=mixed
TimeoutStopSec=120
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
EOF
sudo install -m 0644 "$unit" /etc/systemd/system/kuasar-hong-node.service
prep_unit=$(mktemp)
cat > "$prep_unit" <<EOF
[Unit]
Description=Hong isolated Kuasar storage and registry
After=network-online.target docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
User=root
Environment=DEMO_DATA_DIR=$DATA
Environment=BIN=$BIN
Environment=ZOT_BIN=$ROOT/build/e2e-tools/x86_64/zot
Environment=E2E_IMAGE=sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79
Environment=DEMO_QUICKSTART=1
ExecStart=/bin/bash $STATE/prep-hong-node.sh
ExecStop=/bin/bash $STATE/prep-hong-node.sh stop
TimeoutStartSec=600
TimeoutStopSec=120
[Install]
WantedBy=multi-user.target
EOF
sudo install -m 0644 "$prep_unit" /etc/systemd/system/kuasar-hong-prep.service
rm -f "$prep_unit"
sudo systemctl daemon-reload
sudo systemctl enable kuasar-hong-prep.service kuasar-hong-node.service
sudo systemctl start kuasar-hong-node.service
printf 'Started. Inspect: sudo journalctl -u kuasar-hong-node -f\n'
