import subprocess as sp,time,pwd
from pathlib import Path
uid=pwd.getpwnam('bench108-agent').pw_uid
seen={}
while True:
 for p in Path('/sys/class/ublk-char').glob('ublkc*'):
  d=Path('/dev')/p.name
  try:ino=d.stat().st_ino
  except FileNotFoundError:continue
  if seen.get(p.name)==ino:continue
  q=sp.run(['/opt/bench108/deploy/ublk-owner',p.name],capture_output=True,text=True)
  if q.returncode or q.stdout.strip()!=str(uid):continue
  for name in [p.name,p.name.replace('ublkc','ublkb')]:
   node=Path('/dev')/name
   if node.exists():sp.run(['setfacl','-m',f'u:{uid}:rw',str(node)],check=True)
  if (Path('/dev')/p.name.replace('ublkc','ublkb')).exists():seen[p.name]=ino
 time.sleep(.02)
