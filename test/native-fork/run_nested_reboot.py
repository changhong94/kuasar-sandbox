#!/usr/bin/env python3
"""Reset only a newly spawned outer VM, preserving its private durable disk."""
import argparse,json,pathlib,subprocess,time,os
p=argparse.ArgumentParser();p.add_argument('--ch',required=True);p.add_argument('--work',required=True);a=p.parse_args()
w=pathlib.Path(a.work).resolve();assert os.geteuid()==0
assert all((w/n).is_file() for n in ('disk.raw','kernel','initramfs'))
assert not (w/'serial-capture.log').exists(),'use a fresh build directory'
results=[]
for phase,marker in (('capture','NESTED_DURABLE_READY'),('restore','NESTED_VERIFIED ')):
 serial=w/('serial-'+phase+'.log');sock='/tmp/native-nested-'+str(os.getpid())+'-'+phase+'.sock'
 args=[a.ch,'--cpus','boot=2,nested=on','--memory','size=4G','--kernel',str(w/'kernel'),'--initramfs',str(w/'initramfs'),'--cmdline','console=ttyS0 panic=-1','--disk','path='+str(w/'disk.raw')+',image_type=raw','--console','off','--serial','file='+str(serial),'--api-socket',sock]
 with (w/('vmm-'+phase+'.log')).open('wb') as log:
  child=subprocess.Popen(args,stdout=log,stderr=log)
  try:
   end=time.monotonic()+300
   while time.monotonic()<end:
    text=serial.read_text(errors='replace') if serial.exists() else ''
    if 'NESTED_FAILED' in text:raise RuntimeError(text[-12000:])
    if marker in text:
     if phase=='restore':results=json.loads(text.split(marker,1)[1].splitlines()[0])
     break
    if child.poll() is not None:raise RuntimeError('outer VM exited: '+(w/('vmm-'+phase+'.log')).read_text())
    time.sleep(.2)
   else:raise TimeoutError(phase)
  finally:
   # No global process search/kill: only the child handle owned by this test.
   if child.poll() is None:child.kill()
   child.wait(timeout=30)
   pathlib.Path(sock).unlink(missing_ok=True)
report={'passed':True,'scope':'hard reset of isolated nested Linux host, not physical host power loss','outer_memory_gib':4,'outer_vcpus':2,'restored_last_durable_checkpoint_only':True,'results':results}
(w/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
