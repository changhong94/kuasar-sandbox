from pathlib import Path
root=Path.home()/"src"
repo=root/"kuasar-sandbox/kuasar-sandbox"
s=(repo/"test/demo/demo_prep.sh").read_text()
line='SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
assert s.count(line)==1
s=s.replace(line,'SCRIPT_DIR="'+str(repo/'test/demo')+'"')
marker='BASE_TAG="sha-${SOURCE_IMAGE_ID#sha256:}"'
insert='''# Docker containerd image IDs may identify a manifest rather than its config.
# Derive the config identity from the exact local image's exported content.
docker image save "$SOURCE_IMAGE_ID" -o "$LOG_DIR/source-image.tar"
SOURCE_CONFIG_DIGEST="$(python3 - "$LOG_DIR/source-image.tar" <<'PYDIGEST'
import hashlib,json,sys,tarfile
with tarfile.open(sys.argv[1]) as t:
    entries=json.load(t.extractfile("manifest.json"))
    assert len(entries)==1, "expected exactly one exported image"
    config=t.extractfile(entries[0]["Config"]).read()
    print("sha256:"+hashlib.sha256(config).hexdigest())
PYDIGEST
)"
'''
assert s.count(marker)==1
s=s.replace(marker,insert+marker)
old='[ "$config_digest" = "$SOURCE_IMAGE_ID" ]'
assert s.count(old)==1
s=s.replace(old,'[ "$config_digest" = "$SOURCE_CONFIG_DIGEST" ]')
p=root/".deployment/prep-hong-node.sh";p.write_text(s);p.chmod(0o700)
print(p)