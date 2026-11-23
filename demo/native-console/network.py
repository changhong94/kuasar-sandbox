#!/usr/bin/env python3
"""Configure only the dedicated native-console namespace and management route."""
import subprocess,sys,time,pathlib
name='fnative';ns='fnative-ns';dev='fnative-m0'
def run(*args):subprocess.run(args,check=True)
if sys.argv[1]=='prepare':
 if not pathlib.Path('/run/netns/'+ns).exists():run('ip','netns','add',ns)
 run('ip','-n',ns,'link','set','lo','up');pathlib.Path('/run/forklab-native').mkdir(exist_ok=True,mode=0o700)
else:
 end=time.monotonic()+30
 while not pathlib.Path('/sys/class/net/'+dev).exists():
  if time.monotonic()>end:raise TimeoutError(dev)
  time.sleep(.1)
 run('ip','addr','replace','169.254.169.251/32','dev',dev)
 run('ip','route','replace','100.126.0.0/19','dev',dev)
