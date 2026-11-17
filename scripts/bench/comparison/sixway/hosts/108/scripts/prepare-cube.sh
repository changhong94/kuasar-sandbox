#!/bin/bash
set -euo pipefail
M=/opt/bench108
D=$M/deploy/cube
mkdir -p "$D" "$M/data/cube" "$M/data/cube-toolbox"
for pair in "$M/data/cube:/data" "$M/data/cube-toolbox:/usr/local/services/cubetoolbox"; do
 src=${pair%:*};dst=${pair#*:};mkdir -p "$dst"
 if ! mountpoint -q "$dst";then test -z "$(ls -A "$dst")";mount --bind "$src" "$dst";fi
 test "$(stat -c '%d:%i' "$src")" = "$(stat -c '%d:%i' "$dst")"
done
if ! test -e /run/netns/b108-cube; then
 ip netns add b108-cube
 ip -n b108-cube link set lo up
 ip -n b108-cube link add b0 type dummy
 ip -n b108-cube addr add 192.0.2.108/24 dev b0
 ip -n b108-cube link set b0 up
 ip -n b108-cube route add default via 192.0.2.1
fi
ip netns exec b108-cube sysctl -qw net.ipv4.ip_forward=1
printf '{"log-driver":"local","default-address-pools":[{"base":"172.28.0.0/16","size":24}]}\n' > "$D/dockerd.json"
cat > /etc/systemd/system/bench108-cube-docker.service <<EOF
[Unit]
Description=Sixway108 private Cube Docker daemon
[Service]
Type=notify
NetworkNamespacePath=/run/netns/b108-cube
RuntimeDirectory=bench108-cube-docker
ExecStart=/usr/bin/dockerd --config-file=$D/dockerd.json --host=unix:///run/bench108-cube-docker/docker.sock --pidfile=/run/bench108-cube-docker/docker.pid --exec-root=/run/bench108-cube-docker/exec --data-root=$M/data/cube-docker --bridge=none --containerd-namespace=bench108-cube --containerd-plugins-namespace=bench108-cube-plugins
Delegate=yes
LimitNOFILE=1048576
EOF
mkdir -p /etc/systemd/system/cube-sandbox-.service.d
cat > /etc/systemd/system/cube-sandbox-.service.d/bench108.conf <<EOF
[Service]
Environment=DOCKER_HOST=unix:///run/bench108-cube-docker/docker.sock
NetworkNamespacePath=/run/netns/b108-cube
EOF
# The SDK resolves the private benchmark domain explicitly, as on 113.
# Do not send DNS configuration to the host's systemd-resolved over D-Bus.
mkdir -p /etc/systemd/system/cube-sandbox-dns-host-route.service.d
printf '[Service]\nExecStart=\nExecStart=/bin/true\nExecStop=\n' > /etc/systemd/system/cube-sandbox-dns-host-route.service.d/bench108.conf
systemctl daemon-reload
systemctl start bench108-cube-docker
export DOCKER_HOST=unix:///run/bench108-cube-docker/docker.sock
docker load -i "$M/import113/comparison/assets/cube-support-images.tar"
