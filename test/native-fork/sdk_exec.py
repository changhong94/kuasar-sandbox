#!/usr/bin/env python3
"""Exercise the installed E2B SDK; secrets are supplied only on stdin."""
import json,shlex,sys
from e2b import Sandbox
r=json.load(sys.stdin)
s=Sandbox.connect(r['id'],api_key=r['key'],api_url=r['api'],sandbox_url=r['proxy'])
if r.get('action')=='file-write':
 s.files.write('/root/sdk-value',r['code'],user='root');sys.exit(0)
if r.get('action')=='file-read':
 sys.stdout.write(s.files.read('/root/sdk-value',user='root'));sys.exit(0)
if r.get('action')=='fork':
 child=s.fork(count=1,timeout=300)[0]
 if isinstance(child,Exception):raise child
 print(json.dumps({'sandboxID':child.sandbox_id}));sys.exit(0)
command=r['code'] if r.get('action')=='command' else '/usr/local/bin/python3 -c '+shlex.quote(r['code'])
result=s.commands.run(command,user='root',cwd='/',background=r.get('background',False))
if r.get('background'): print(result.pid)
else:
 sys.stdout.write(result.stdout)
 if result.exit_code:sys.stderr.write(result.stderr);sys.exit(result.exit_code)
