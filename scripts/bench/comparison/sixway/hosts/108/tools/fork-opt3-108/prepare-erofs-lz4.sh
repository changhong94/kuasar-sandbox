set -eu
M=/opt/bench108
T=$M/tools/fork-opt3-108
R=$M/results/fork-opt3-108
mount --make-rprivate /
mkdir -p "$T/mount-ext4" "$T/mount-erofs"
trap 'umount "$T/mount-erofs" 2>/dev/null || true; umount "$T/mount-ext4" 2>/dev/null || true' EXIT
mount -o loop,ro "$M/assets/python-base.ext4" "$T/mount-ext4"
time "$T/erofs-utils/mkfs/mkfs.erofs" --preserve-mtime -zlz4hc -C32768 -E force-inode-extended "$M/assets/python-base-fork-opt3-lz4.erofs" "$T/mount-ext4"
chmod 444 "$M/assets/python-base-fork-opt3-lz4.erofs"
mount -t erofs -o loop,ro "$M/assets/python-base-fork-opt3-lz4.erofs" "$T/mount-erofs"
"$M/venv/bin/python" "$T/fs-manifest.py" "$T/mount-ext4" "$R/fs-ext4.json"
"$M/venv/bin/python" "$T/fs-manifest.py" "$T/mount-erofs" "$R/fs-erofs.json"
"$M/venv/bin/python" - "$R" <<'PY'
import json,sys
from pathlib import Path
r=Path(sys.argv[1]);a=json.loads((r/'fs-ext4.json').read_text());b=json.loads((r/'fs-erofs.json').read_text());assert a==b,[(k,a.get(k),b.get(k)) for k in a.keys()|b.keys() if a.get(k)!=b.get(k)][:5]
(r/'filesystem-equivalence.json').write_text(json.dumps({'identical':True,'entries':len(a),'checked':['file contents','uid','gid','mode','mtime_ns','symlink targets','xattrs','device IDs']}));print('FILESYSTEM IDENTICAL',len(a))
PY
