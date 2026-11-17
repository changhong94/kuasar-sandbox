from pathlib import Path
import subprocess as sp,time,json,fcntl
B=Path('/home/hong/src/research/sixway-aligned-20261117');digest='sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79'
lock=open('/run/skyrl-threeway-benchmark.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
rows=[]
for path in [B/'results/agentenv-template.log',B/'results/template-preparation.json']:
 if path.exists():path.rename(path.with_suffix(path.suffix+'.attempt-'+str(time.time_ns())))
def run(n,args):
 t=time.monotonic();start=time.time_ns()
 with (B/'results'/(n+'.log')).open('w') as f:r=sp.run(args,stdout=f,stderr=sp.STDOUT)
 rows.append(dict(product=n,start_unix_ns=start,elapsed_ms=(time.monotonic()-t)*1000,returncode=r.returncode,command=args))
 (B/'results/template-preparation.json').write_text(json.dumps(rows,indent=2));assert r.returncode==0,n
run('agentenv-template',['nsenter','--net=/run/netns/bench113','env','XDG_CONFIG_HOME=/home/hong/deploy/comparison/client','/opt/agentenv-comparison/v0.2.4/aenv','pull','127.0.0.1:5000/e2b/base@'+digest,'--name','aligned-python-2cpu-v3','--cpu','2','--memory','2048','--start-cmd','/bin/sleep infinity','--ready-cmd','/bin/true','--timeout','600'])
run('cube-template',['nsenter','--net=/run/netns/bench113','/usr/local/bin/cubemastercli','--address','127.0.0.1','--timeout','15m','tpl','create-from-image','--image','http://127.0.0.1:5000/e2b/base@'+digest,'--alias','aligned-python-2cpu-v3','--writable-layer-size','1G','--expose-port','49983','--probe','49983','--probe-path','/health','--enable-inject-envd','--envd-path','/home/hong/deploy/comparison/assets/cube-envd','--cpu','2000','--memory','2048','--cmd','/bin/sh','--arg=-c','--arg=id user >/dev/null 2>&1 || useradd -m -u 1000 -s /bin/bash user; exec /bin/sleep infinity','--json'])
