#!/usr/bin/env python3
"""Private-RAM/VMM transport gate; not the native conductor integration test."""
import argparse,os,pathlib,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--ch-repo',required=True);p.add_argument('--exporter',required=True);p.add_argument('--kernel',required=True);p.add_argument('--work',required=True);a=p.parse_args()
repo=pathlib.Path(a.ch_repo).resolve();out=pathlib.Path(a.work).resolve();out.mkdir(mode=0o700,exist_ok=False);(out/'root').mkdir()
subprocess.run(['cc','-std=c11','-O2','-static','-Wall','-Wextra','-Werror','-DFORK_SERIAL_CONTROL',str(repo/'scripts/research/linux-fork-init.c'),'-o',str(out/'root/init')],check=True)
with (out/'initramfs.cpio').open('wb') as f:subprocess.run(['cpio','--quiet','-o','-H','newc'],input=b'init\n',cwd=out/'root',stdout=f,check=True)
with (out/'disk.raw').open('wb') as f:f.write(b'fork-device-state');f.truncate(1048576)
with (out/'export.log').open('w') as log:
 server=subprocess.Popen([a.exporter,'--socket',str(out/'disk.sock'),'--disk',str(out/'disk.raw')],stdout=log,stderr=log)
 try:
  for _ in range(100):
   if (out/'disk.sock').exists():break
   if server.poll() is not None:raise RuntimeError('export failed')
   time.sleep(.02)
  else:raise TimeoutError('export socket')
  env=os.environ.copy();env['NATIVE_DISK_SOCKET']=str(out/'disk.sock');env['CH_FORK_ACCOUNT_PSS']='1';env['CH_FORK_TIMING']='1'
  with (out/'test.log').open('w') as f:
   subprocess.run(['python3',str(repo/'scripts/research/test-http-fork.py'),str(repo/'target/debug/cloud-hypervisor'),a.kernel,str(out/'initramfs.cpio'),str(out)],env=env,stdout=f,stderr=f,check=True,timeout=240)
 finally:
  server.terminate()
  try:server.wait(timeout=20)
  except subprocess.TimeoutExpired:server.kill();server.wait();raise
print((out/'results.json').read_text())
