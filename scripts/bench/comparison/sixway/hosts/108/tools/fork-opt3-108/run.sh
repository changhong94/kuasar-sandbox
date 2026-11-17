set -eu
M=/opt/bench108
R=$M/results/fork-opt3-108
T=$M/tools/fork-opt3-108
round=$1
date -u '+%Y-%m-%d %H:%M:%S UTC' > "$R/$round-start.txt"
sudo "$M/venv/bin/python" "$T/bench.py" "$T/config.json" --out "$R/$round"
sudo journalctl -u bench108-fork --since "$(cat "$R/$round-start.txt")" -o cat > "$R/$round-server.log"
sudo cp "$M/data/mlink/ttlet.log" "$R/$round-mlink.log"
