from pathlib import Path
import subprocess as s,json,sys,time,shlex,os,urllib.request,shutil
r=Path(__file__).resolve().parent;d=r/'deployment/fork';data=r/'runtime-media/volume/fork';v='sixway-20261119-fork-vmm.service';a='sixway-20261119-fork-api.service';e=r/'attempts'/('repair-fork-'+str(time.time_ns()));e.mkdir();q=Path('/home/hong/src/research/sandbox_fork/kuasar-io/kuasar');sys.path.insert(0,str(q/'integrations/e2b'));import vm_rpc
def run(*argv,**kw):return s.run(argv,check=True,**kw)
def rpc(action,**kw):return vm_rpc.admin('/run/sx19fork/admin.sock',action,**kw)
def dump(k,x):(e/k).write_text(json.dumps(x,indent=2))
env=shlex.split(s.check_output(['systemctl','show',a,'-p','Environment','--value'],text=True))
sid='sx19seed0001';ns='sixway19-fork';seed='sixway19-seed';old=Path('/home/hong/src/research/python-latest-113')
gate=urllib.request.Request('http://127.0.0.1:18887/template-pool',data=b'{"drain":true}',headers={'X-API-Key':(d/'api-key').read_text().strip(),'Content-Type':'application/json'})
dump('before.json',rpc('sandbox-list'))
with urllib.request.urlopen(gate,timeout=180) as response:remaining=json.load(response)
dump('drain.json',remaining);assert remaining['owned']==remaining['assigned']==0
run('systemctl','stop',a);rpc('sandbox-destroy',sandbox_id=sid);dump('after.json',rpc('sandbox-list'));assert not list((data/'state').iterdir())
run('ip','netns','exec',ns,'env','CNI_COMMAND=DEL','CNI_CONTAINERID='+sid,'CNI_IFNAME=eth0','CNI_NETNS=/run/netns/'+seed,'CNI_PATH='+str(old/'assets/cni'),old/'assets/cni/bridge',input=(d/'cni.json').read_text(),text=True)
run('systemctl','stop',v);args=json.loads(next((r/'attempts').glob('fork-control-*/launch2.json')).read_text());at=args.index('/usr/bin/env')
args[at:at]=['--setenv=CH_FORK_TIMING=1','--setenv=CH_RESTORE_TIMING=1','--setenv=KUASAR_SNAPSHOT_POOL_ROOT='+str(data/'snapshot-templates'),'--setenv=KUASAR_CHECKPOINT_MANIFEST_CONFIG='+str(d/'manifest.yaml'),'--setenv=KUASAR_CHECKPOINT_MANIFEST_RAW=/home/hong/src/research/report-revision-113/bin/manifest-raw']
worker=data/'worker3.ext4';run('cp','--sparse=always','/home/hong/src/research/ready-regression-113/oci-worker-uniform-prefork.ext4',worker);worker.chmod(0o400)
conf=d/'config.toml';conf.write_text(conf.read_text().replace(str(data/'worker2.ext4'),str(worker)).replace('live_fork_writable_disk=true','live_fork_writable_disk=false'));dump('launch.json',args);run(*args)
for _ in range(100):
 try:rpc('sandbox-list');break
 except OSError:time.sleep(.1)
src=(d/'api.initial.py').read_text().replace("P/'bin/image-mount'","B/'deploy/fork/bin/image-mount'").replace("sandbox_id=sid,netns=ns","sandbox_id=sid,netns='/run/netns/'+name")
(d/'api.py').write_text(src)
run('systemd-run','--unit='+a,'-p','NetworkNamespacePath=/run/netns/'+ns,'-p','LimitNOFILE=65536',*['--setenv='+x for x in env],'/usr/bin/python3',d/'api.py')
os.execv('/usr/bin/python3',['python3',str(r/'live-cohort.py')])
