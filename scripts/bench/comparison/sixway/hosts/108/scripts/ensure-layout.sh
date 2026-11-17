#!/bin/bash
set -euo pipefail
M=/home/huawei/src/research/sixway_startup_108
bash "$M/scripts/prepare-storage.sh"
for name in b108-off b108-uffd b108-agent b108-mlink b108-fork b108-cube; do
 if ! test -e /run/netns/"$name"; then ip netns add "$name"; fi
 ip -n "$name" link set lo up
 ip netns exec "$name" sysctl -qw net.ipv4.ip_forward=1
done
for name in b108-off b108-uffd b108-cube; do
 if ! ip -n "$name" link show b0 >/dev/null 2>&1; then
  ip -n "$name" link add b0 type dummy
  ip -n "$name" addr add 192.0.2.108/24 dev b0
  ip -n "$name" link set b0 up
  ip -n "$name" route add default via 192.0.2.1
 fi
done
ip -n b108-cube addr show lo | grep -q '169.254.253.53/' || ip -n b108-cube addr add 169.254.253.53/32 dev lo
for pair in "$M/data/cube:/data" "$M/data/cube-toolbox:/usr/local/services/cubetoolbox";do
 src=${pair%:*};dst=${pair#*:}
 test -d "$src";mkdir -p "$dst"
 if ! mountpoint -q "$dst";then test -z "$(ls -A "$dst")";mount --bind "$src" "$dst";fi
 test "$(stat -c '%d:%i' "$src")" = "$(stat -c '%d:%i' "$dst")"
done

modprobe ublk_drv
setfacl -m u:bench108-agent:rw /dev/ublk-control
