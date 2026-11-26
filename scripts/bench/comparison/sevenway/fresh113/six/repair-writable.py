from pathlib import Path
import sys,json,subprocess as s,time,os,shlex
from urllib.request import Request,urlopen
r=Path(__file__).resolve().parent;d=r/'deployment/fork';q=Path('/home/hong/src/research/sandbox_fork/kuasar-io/kuasar');f=q/'integrations/e2b/writable_root.py';e=r/'attempts'/('writable-repair-'+str(time.time_ns()));e.mkdir()
assert s.check_output(['runuser','-u','hong','--','git','-C',q,'branch','--show-current'],text=True).strip()=='sandbox_fork_staging'
t=f.read_text();target='    directory.mkdir(mode=0o700)';assert t.count(target)==1
# The app-write disk and the writable boot disk share the sandboxer's managed directory.
t=t.replace(target,'''    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Invalid managed disk directory')''')
# Request exclusive creation before cp so an existing private base is never overwritten.
t=t.replace("    subprocess.run(['cp'", "    with source.open('xb'):\n        pass\n    if os.path.lexists(leaf):\n        raise FileExistsError(leaf)\n    subprocess.run(['cp'")
f.write_text(t);compile(t,str(f),'exec');(e/'repair.patch').write_bytes(s.check_output(['runuser','-u','hong','--','git','-C',q,'diff','--',str(f)]))
cfg=json.loads((d/'benchmark-config.json').read_text())['kuasar-fork'];req=Request(cfg['api_url']+'/template-pool',data=b'{"drain":true}',headers={'X-API-Key':Path(cfg['key_file']).read_text().strip(),'Content-Type':'application/json'})
with urlopen(req,timeout=180) as res:status=json.load(res)
assert status['owned']==status['assigned']==0;(e/'drain.json').write_text(json.dumps(status))
a=d/'api.py';src=a.read_text();(e/'api-before.py').write_text(src);a.write_text(src[:src.index("if not Path('/run/netns/'+name)")]+src[src.index("os.environ['E2B_IMAGE_MOUNT_HELPER']"):])
s.run(['systemctl','restart','sixway-20261119-fork-api'],check=True)
os.execv('/usr/bin/python3',['python3',str(r/'live-cohort.py')])
