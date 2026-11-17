import json,os
from pathlib import Path
p=Path('/opt/bench108/deploy/fork/images.json');d=json.loads(p.read_text())
r=Path('/opt/bench108/results/no-python-warm-108')
(r/'imported-catalog.json').write_text(json.dumps(d,indent=2))
for name in ['node','ruby']:
 assert not d[name].get('startup_read_files')
 # Keep language interpreters out of template preparation. This is the same
 # keep-alive entrypoint override for both images, with their OCI Env intact.
 d[name]['oci_config']['Entrypoint']=['/bin/sh','-c']
 d[name]['oci_config']['Cmd']=['exec sleep infinity']
t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2))
with t.open('rb') as f:os.fsync(f.fileno())
t.replace(p);fd=os.open(p.parent,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
(r/'deployed-catalog.json').write_text(json.dumps(d,indent=2))
