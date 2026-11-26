from pathlib import Path
import json,os,subprocess as sp,hashlib,time
r=Path(__file__).resolve().parent
def run(*args): return sp.check_output(args,text=True).strip()
unit='sixway-20261119-fork-vmm.service'; ns='sixway19-fork'; runtime=Path('/run/sx19fork'); mp=r/'runtime-media/volume'; data=mp/'fork'; deploy=r/'deployment/fork'
assert run('findmnt','-no','UUID','--mountpoint',mp)=='95c37d08-70e3-41c9-9699-229eeb965ebd'
assert run('systemctl','show','-p','LoadState','--value',unit)=='not-found'
assert not any(x.exists() for x in [Path('/run/netns')/ns,runtime,data,deploy])
e=r/'attempts'/('fork-control-'+str(time.time_ns())); e.mkdir()
for name,cmd in {'users':['systemctl','list-units','--all','user@*.service'],'sockets':['ss','-xlpn'],'container-processes':['ps','-eo','pid,user,comm,cgroup'],'units':['systemctl','list-unit-files'],'netns':['ip','netns','list'],'loop':['losetup','-J'],'mount':['findmnt','--json']}.items():
 (e/name).write_text(run(*cmd))
ledger=r/'ownership.json';j=json.loads(ledger.read_text());j['fork_control']={'system_unit':unit,'transient_file':'/run/systemd/transient/'+unit,'netns':ns,'runtime':str(runtime),'data':str(data),'deploy':str(deploy),'original':'absent','evidence':str(e),'unix_sockets':[str(runtime/x) for x in ['admin.sock','service.sock']]}
def save():
 t=ledger.with_suffix('.next');t.write_text(json.dumps(j,indent=2));os.chown(t,ledger.stat().st_uid,ledger.stat().st_gid);t.replace(ledger)
save()
deploy.mkdir(parents=True); data.mkdir();runtime.mkdir();(runtime/'empty').mkdir();(data/'state').mkdir()
src=Path('/home/hong/src/research/python-latest-113/deploy/fork')
conf=(src/'config.toml').read_text();old='/home/hong/src/research/ready-regression-113/oci-worker-uniform-prefork.ext4'
run('cp','--sparse=always',old,data/'worker.ext4')
for a,b in [(str(src/'bin/cloud-hypervisor'),str(r/'bin/cloud-hypervisor')),(old,str(data/'worker.ext4')),('live_fork_writable_disk=false','live_fork_writable_disk=true')]:
 assert conf.count(a)==1;conf=conf.replace(a,b)
(deploy/'config.toml').write_text(conf)
for stamp in ['cloud-hypervisor','vmm-sandboxer']:
 for name,h in json.loads((r/(stamp+'.json')).read_text())['hashes'].items():assert hashlib.sha256((r/'bin'/name).read_bytes()).hexdigest()==h
run('ip','netns','add',ns);j['fork_control']['namespace_inode']=(Path('/run/netns')/ns).stat().st_ino;save()
run('ip','-n',ns,'link','set','lo','up')
args=['systemd-run','--unit='+unit,'-p','NetworkNamespacePath=/run/netns/'+ns,'-p','TemporaryFileSystem=/run/containerd','-p','PrivateTmp=yes','--setenv=KUASAR_CONTAINERD_TTRPC_ADDRESS='+str(runtime/'unused.ttrpc'),'--setenv=KUASAR_FORK_RUNTIME_DIR='+str(runtime),str(r/'bin/cloud_hypervisor'),'--config',str(deploy/'config.toml'),'--dir',str(data/'state'),'--listen',str(runtime/'service.sock'),'--admin-listen',str(runtime/'admin.sock')]
(e/'launch.json').write_text(json.dumps(args));run(*args)
for i in range(100):
 if (runtime/'admin.sock').is_socket():break
 time.sleep(.1)
assert (runtime/'admin.sock').is_socket()
(e/'unit').write_text(run('systemctl','show',unit,'-p','MainPID','-p','ControlGroup','-p','ActiveState'));print(e)
