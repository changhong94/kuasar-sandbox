#!/bin/bash
set -euo pipefail
M=/home/huawei/src/research/sixway_startup_108
img=$M/data.xfs
mp=$M/data
if ! test -f "$img"; then
 (set -C; : > "$img")
 truncate -s 128G "$img"
 mkfs.xfs -m reflink=1 "$img" > "$M/results/mkfs.log"
fi
mkdir -p "$mp"
if ! mountpoint -q "$mp"; then
 test -z "$(ls -A "$mp")"
 mount -o loop,noatime "$img" "$mp"
fi
test "$(findmnt -no FSTYPE "$mp")" = xfs
chown huawei:huawei "$mp"
