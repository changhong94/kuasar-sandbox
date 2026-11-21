#!/usr/bin/env python3
"""Configure only the dedicated native-console namespace and management route."""
import subprocess,sys,time,pathlib
name='fork2sw';ns='fork2sw-ns';dev='fork2sw-m0'
def run(*args):subprocess.run(args,check=True)
if sys.argv[1]=='prepare':
 if not pathlib.Path('/run/netns/'+ns).exists():run('ip','netns','add',ns)
 run('ip','-n',ns,'link','set','lo','up');pathlib.Path('/run/fork2').mkdir(exist_ok=True,mode=0o700)
else:
 end=time.monotonic()+30
 while not pathlib.Path('/sys/class/net/'+dev).exists():
  if time.monotonic()>end:raise TimeoutError(dev)
  time.sleep(.1)
 run('ip','addr','replace','169.254.169.252/32','dev',dev)
 run('ip','route','replace','100.128.0.0/19','dev',dev)
