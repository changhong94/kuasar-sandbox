from pathlib import Path
import sys,json,shlex
sys.path.insert(0,str(Path(__file__).parent))
import runner as b
p=sys.argv[1];out=Path(sys.argv[2]);b.pr=p;b.setup(p);s=None
identity=json.loads(Path('/home/hong/deploy/kuasar-fork-research/image-identity.json').read_text())
paths=['usr/local/bin/python3.12','usr/local/lib/libpython3.12.so.1.0','usr/lib/x86_64-linux-gnu/libc.so.6','usr/lib/x86_64-linux-gnu/libcrypto.so.3']
try:
 s=b.create();platform=b.cmd(s,'nproc; grep MemTotal /proc/meminfo; python3 --version');assert platform.splitlines()[0]=='1' and 'Python 3.12.14' in platform,platform
 hashes=b.cmd(s,'sha256sum '+' '.join(shlex.quote('/'+p) for p in paths));actual={line.split()[1].lstrip('/'):line.split()[0] for line in hashes.splitlines()}
 for f in paths:assert actual[f]==identity['base_files'][f],(p,f)
 out.write_text(json.dumps({'product':p,'platform':platform,'verified_files':actual,'base_manifest_digest':identity['base_manifest_digest'],'success':True},indent=2))
finally:
 if s:b.kill(s)
