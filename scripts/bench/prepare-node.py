#!/usr/bin/env python3
"""Generate a persistent isolated node from the checked-out official Demo setup."""
from pathlib import Path
import json,subprocess
root=Path.home()/"src"
repo=root/"kuasar-sandbox/kuasar-sandbox"
state=root/".deployment"
src=repo/"test/demo/demo_e2b.sh"
s=src.read_text()
marker='banner "Spawn a real microVM sandbox (Sandbox.create)"'
assert s.count(marker)==1
s=s[:s.index(marker)]
line='SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
assert s.count(line)==1
s=s.replace(line,'SCRIPT_DIR="'+str(repo/'test/demo')+'"')
s=s.replace('subjectAltName=DNS:*.$DOMAIN,DNS:$DOMAIN','subjectAltName=DNS:*.$DOMAIN,DNS:$DOMAIN,IP:127.0.0.1,IP:127.0.0.2,IP:10.213.17.53')
s=s.replace('-days 2 -sha256','-days 365 -sha256')
s+='''
# Keep this run-owned node alive for subsequent manually invoked benchmarks.
"$PYTHON_BIN" - "$WORK" "$TEMPLATE" "$AK" "$DOMAIN" "$RUN_ROOT" <<'PYCONFIG'
import json,sys,pathlib,os
work,template,key,domain,runroot=sys.argv[1:]
p=pathlib.Path("/home/hong/src/.deployment/access.json")
data={"api_url":"https://127.0.0.1:443","proxy_url":"https://127.0.0.2:443","domain":domain,"api_key":key,"ca_file":work+"/demo-ca.crt","template_id":template,"work_dir":work,"run_root":runroot,"bin":"/home/hong/src/kuasar-sandbox/kuasar-sandbox/bin/x86_64"}
p.write_text(json.dumps(data,indent=2)+"\\n");p.chmod(0o600)
PYCONFIG
echo "KUASAR_HONG_NODE_READY"
trap 'exit 0' TERM INT
while true; do sleep 60 & wait $!; done
'''
out=state/"serve-hong-node.sh";out.write_text(s);out.chmod(0o700)
print(out)