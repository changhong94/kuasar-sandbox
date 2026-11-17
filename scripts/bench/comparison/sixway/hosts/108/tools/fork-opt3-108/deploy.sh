set -eu
M=/opt/bench108
Q=$M/src/kuasar-fork/kuasar-io/kuasar/integrations/e2b
R=$M/results/fork-opt3-108
T=$M/tools/fork-opt3-108
round=$1
mkdir -p "$R/$round-source"
cp "$Q/image-mount.c" "$Q/slot_disk.py" "$Q/durable_state.py" "$Q/image_pool.py" "$R/$round-source/"
gcc -static -pthread -O2 -Wall -Wextra -Werror "$Q/image-mount.c" -o "$T/image-mount"
sudo cp "$T/image-mount" "$M/deploy/fork/bin/image-mount"
sudo nsenter --net=/run/netns/b108-fork "$M/venv/bin/python" "$M/scripts/reset-fork.py" > "$R/$round-reset.log" 2>&1
sudo nsenter --net=/run/netns/b108-fork "$M/venv/bin/python" "$T/wait-ready.py" > "$R/$round-ready.json"
