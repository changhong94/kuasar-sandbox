from pathlib import Path
import subprocess as sp
B=Path('/home/hong/src/research/sixway-aligned-20261117');p=Path('/home/hong/deploy/mlink-generic/mlink-dev.py');s=p.read_text();(B/'backups/mlink-dev.py').write_text(s)
s=s.replace('time.sleep(.08)','time.sleep(.01)');p.write_text(s)
# Device inventory headroom is not additional ready VM slots; import needs devices beside the two ready slots.
p=Path('/home/hong/deploy/mlink-generic/start.sh');s=p.read_text();needle='load_test_resources 1; write_node_configs 2 1000 2 2 2'
s=s.replace(needle,needle+'\nsed -i \'s/^count = 2$/count = 18/; s/^high_watermark = 4$/high_watermark = 20/\' "$work/ublkd.toml"');p.write_text(s)
sp.run(['systemctl','restart','bench-mlink-generic'],check=True)
