import sys,os,json,time,tempfile,subprocess
from pathlib import Path
M=Path('/opt/bench108');sys.path.insert(0,str(M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'));from image_pool import UnixHTTP
source=Path(json.loads((M/'data/fork/adapter-state.json.snapshot-preparation.json').read_text())['base']['directory']);cfg=json.loads((source/'config.json').read_text())
with tempfile.TemporaryDirectory(prefix='bench108-prepare-') as t:
 t=Path(t);sock=t/'api.sock';log=(t/'vmm.log').open('w');p=subprocess.Popen([str(M/'build/snapshot-ch/release/cloud-hypervisor'),'--api-socket',str(sock)],stdout=log,stderr=log)
 def api(ep,body=None):
  c=UnixHTTP(sock)
  try:
   c.request('PUT','/api/v1/'+ep,None if body is None else json.dumps(body));r=c.getresponse();return r.status,r.read().decode()
  finally:c.close()
 def fds():
  out=[]
  for f in Path(f'/proc/{p.pid}/fd').iterdir():
   try:
    link=os.readlink(f)
    if 'kvm-vm' in link or 'kvm-vcpu' in link:out.append(link)
   except FileNotFoundError:pass
  return sorted(out)
 try:
  for _ in range(100):
   if sock.exists():break
   if p.poll() is not None:raise RuntimeError((t/'vmm.log').read_text())
   time.sleep(.01)
  assert fds()==[]
  status,body=api('vmm.prepare',cfg);assert status==204,(status,body)
  prepared=fds();assert len(prepared)==2,prepared
  duplicate=api('vmm.prepare',cfg);assert duplicate[0]>=400;assert fds()==prepared
  bad=t/'mismatch';bad.mkdir();cfg2=json.loads(json.dumps(cfg));cfg2['cpus']['boot_vcpus']=2;cfg2['cpus']['max_vcpus']=2;(bad/'config.json').write_text(json.dumps(cfg2));(bad/'state.json').symlink_to(source/'state.json');(bad/'memory-ranges').symlink_to(source/'memory-ranges')
  mismatch=api('vm.restore',{'source_url':'file://'+str(bad),'memory_restore_mode':'CopyOnWrite','prefault':False});assert mismatch[0]>=400,mismatch
  assert 'Prepared KVM profile does not match restore' in mismatch[1],mismatch
  assert fds()==[]  # Failed restore follows CH's ordinary delete/cleanup path.
  assert api('vm.delete')[0]==204;assert fds()==[]
  assert api('vmm.prepare',cfg)[0]==204;assert fds()==prepared
  assert api('vm.delete')[0]==204;assert fds()==[]
  result=dict(success=True,prepared_fds=prepared,duplicate=duplicate,mismatch=mismatch,delete_releases_kvm=True,reprepare=True)
  (M/'results/snapshot-opt-108/prepare-api-test.json').write_text(json.dumps(result,indent=2));print(result)
 finally:
  if p.poll() is None:
   try:api('vmm.shutdown')
   except Exception:p.terminate()
  p.wait(timeout=10)
