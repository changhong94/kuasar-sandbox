from pathlib import Path
import fcntl,json,os,subprocess,sys,time
B=Path('/home/hong/src/research/sevenway-current-20261126/six');PY='/home/hong/src/research/python-latest-113/venv/bin/python';cfg=json.loads((B/'tools/config.json').read_text())
products=('kuasar-fork','kuasar-mlink','agentenv','cube','kuasar-off','kuasar-uffd')
units={'kuasar-fork':['bench-python113-fork'],'kuasar-mlink':['bench-mlink-generic'],'cube':['cube-sandbox-cube-api','cube-sandbox-cubelet','cube-sandbox-cubemaster'],'kuasar-off':['kuasar-comparison-node'],'kuasar-uffd':['bench-private-uffd-serve'],'agentenv':['agentenv-comparison']}
logs={'kuasar-fork':['/var/log/bench-python113-refill-scale-fixed.log'],'kuasar-mlink':['/home/hong/data/mlink-generic/ttlet.log','/home/hong/data/mlink-generic/ublkd.log']}
logs['cube']=['/data/log/CubeMaster/cubemaster-req.log','/data/log/Cubelet/Cubelet-req.log']
for p,a in [('kuasar-off','/home/hong/deploy/comparison/kuasar-state/access.json'),('kuasar-uffd','/home/hong/deploy/private-pilot/uffd-state/access.json')]:logs[p]=[str(Path(json.loads(Path(a).read_text())['work_dir'])/'orch.log')]
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for interval in (0,10,25,50,100):
  for product in products:
   out=B/'results/paced'/str(interval)/product;done=out/'result.json'
   if done.exists():
    r=json.loads(done.read_text());assert r['batch_valid'];continue
   if out.exists():raise RuntimeError('Incomplete case requires explicit audit: '+str(out))
   prep=B/'preparation'/str(interval)/product;prep.mkdir(parents=True,exist_ok=True)
   print('START',interval,product,flush=True);started=time.time()
   if product=='kuasar-mlink':
    c=cfg[product];ctl=['nsenter','--net=/run/netns/'+c['netns']]+c['ctl'];assert json.loads(subprocess.check_output(ctl+['list','--json'],text=True))==[]
    subprocess.run(['systemctl','restart','bench-mlink-generic'],check=True)
    deadline=time.monotonic()+180
    while True:
     probe=subprocess.run(ctl+['list','--json'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
     if probe.returncode==0:
      assert json.loads(probe.stdout)==[];break
     if time.monotonic()>deadline:raise RuntimeError('mlink API did not become ready after owned-service restart: '+probe.stderr)
     time.sleep(1)
    with (prep/'template-policy.log').open('w') as f:subprocess.run(['python3','/home/hong/src/research/report-revision-113/tools/switch-language.py',str(B/'tools/config.json'),'python',str(prep)],stdout=f,stderr=subprocess.STDOUT,check=True)
   (prep/'host.json').write_text(json.dumps({'time':time.time(),'preparation_ms':(time.time()-started)*1000,'load':Path('/proc/loadavg').read_text(),'memory':Path('/proc/meminfo').read_text()}))
   offsets={p:(Path(p).stat().st_ino,Path(p).stat().st_size) for p in logs.get(product,[]) if Path(p).exists()};runstart=time.time()
   with (prep/'client.log').open('w') as f:r=subprocess.run(['nsenter','--net=/run/netns/'+cfg[product]['netns'],PY,str(B/'paced256.py'),'--worker',product,'--interval-ms',str(interval)],stdout=f,stderr=subprocess.STDOUT)
   evidence=prep/'server';evidence.mkdir(exist_ok=True)
   for path,(inode,offset) in offsets.items():
    p=Path(path)
    if p.exists() and p.stat().st_ino==inode:
     with p.open('rb') as src,(evidence/p.name).open('wb') as dst:src.seek(offset);dst.write(src.read())
   with (evidence/'journal.log').open('w') as f:
    args=['journalctl','--no-pager','--since','@'+str(runstart)]
    for u in units[product]:args+=['-u',u]
    subprocess.run(args,stdout=f,stderr=subprocess.STDOUT)
   if r.returncode:raise RuntimeError('Case failed collection/cleanup: '+str(prep/'client.log'))
   result=json.loads(done.read_text());assert result['batch_valid']
   print('DONE',interval,product,result['print']['completed'],result['print']['all_256_ms'],flush=True)
 (B/'paced-complete.json').write_text(json.dumps({'complete':True,'products':6,'interval_ms':[0,10,25,50,100],'requests_per_case':256,'time':time.time()}))
