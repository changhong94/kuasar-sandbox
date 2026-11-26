from pathlib import Path
import sys,json,shlex,subprocess,os
import startup as bench
B=Path('/home/hong/src/research/sevenway-current-20261126/six');c=json.loads((B/'tools/config.json').read_text());n=sys.argv[1]
x,S=bench.setup(n,c);s=None
command='nproc; python3 --version; sha256sum /usr/local/bin/python3.12 /usr/local/lib/libpython3.12.so.1.0 /usr/lib/x86_64-linux-gnu/libc.so.6 /usr/lib/x86_64-linux-gnu/libcrypto.so.3'
identity=json.loads(Path('/home/hong/deploy/kuasar-fork-research/image-identity.json').read_text())
try:
 if S:
  s=S.create(x['template'],timeout=180,**x.get('create_kwargs',{}));sid=s.sandbox_id
  pristine=s.commands.run("for f in /proc/[0-9]*/comm; do cat \"$f\"; done",user='root',timeout=60);assert pristine.exit_code==0;assert not any(v.startswith('python') for v in pristine.stdout.splitlines()),pristine.stdout
  r=s.commands.run(command,user='root',timeout=60);assert r.exit_code==0;r=r.stdout
 else:
  s=subprocess.check_output(x['ctl']+['start',x['template'],'--insecure','--timeout','180'],text=True).strip();sid=s
  pristine=subprocess.check_output(x['ctl']+['exec',s,'--insecure','--user','root','--','/bin/sh','-c','for f in /proc/[0-9]*/comm; do cat "$f"; done'],text=True);assert not any(v.startswith('python') for v in pristine.splitlines()),pristine
  r=subprocess.check_output(x['ctl']+['exec',s,'--insecure','--user','root','--','/bin/bash','-l','-c',command],text=True)
 lines=r.strip().splitlines();assert lines[0]=='2' and lines[1]=='Python 3.12.14',lines[:2]
 hashes={line.split()[1].lstrip('/'):line.split()[0] for line in lines[2:]}
 for k,v in hashes.items():assert identity['base_files'][k]==v,(n,k)
 result=dict(product=n,success=True,platform=lines[:2],hashes=hashes,image_digest=identity['base_manifest_digest'],sandbox_id=sid)
finally:
 if s:
  if S:s.kill()
  else:subprocess.run(x['ctl']+['delete',s],check=True,stdout=subprocess.DEVNULL)
(B/'results'/('preflight-'+n+'.json')).write_text(json.dumps(result,indent=2));print(n,'preflight passed')
