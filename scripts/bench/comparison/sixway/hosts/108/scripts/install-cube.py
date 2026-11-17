#!/usr/bin/env python3
import hashlib,json,os,secrets,subprocess as sp
from pathlib import Path
D=Path('/opt/bench108/import113/comparison'); A=D/'assets';R=Path('/opt/bench108/deploy/cube/cube-sandbox-one-click-v0.7.3-amd64'); data=Path('/opt/bench108/data/cube-support')
os.environ['DOCKER_HOST']='unix:///run/bench108-cube-docker/docker.sock'
asset=next(a for a in json.loads((A/'CubeSandbox-release.json').read_text())['assets'] if a['name']==R.name+'.tar.gz')
with (A/asset['name']).open('rb') as f:assert 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()==asset['digest']
assert sp.check_output(['docker','info','--format','{{.DockerRootDir}}'],text=True).strip()=='/opt/bench108/data/cube-docker'
if not Path('/sys/kernel/btf/vmlinux').is_file():
 raise SystemExit('Cubelet needs BTF for the running kernel. No Cube installation or restart attempted.')
cfg=dict(ONE_CLICK_DEPLOY_ROLE='control',CUBE_PVM_ENABLE='0',CUBE_SANDBOX_NODE_IP='192.0.2.108',CUBE_SANDBOX_NETWORK_CIDR='10.240.0.0/18',CUBE_PROXY_HTTPS_PORT='8443',CUBE_PROXY_HTTP_PORT='8080',CUBE_PROXY_RESOLVED_DNS_ADDR='169.254.253.53',CUBE_API_BIND='127.0.0.1:3000',CUBE_API_HEALTH_ADDR='127.0.0.1:3000',CUBE_API_SANDBOX_DOMAIN='cube.app:8443',CUBE_OPS_BIND='127.0.0.1:3010',WEB_UI_ENABLE='0',ONE_CLICK_ENABLE_TENCENT_DOCKER_MIRROR='0',ONE_CLICK_ENABLE_S3LVOL='0',CUBE_SANDBOX_MINIO_API_BIND='127.0.0.1')
for k in ('CUBE_API_KEY','CUBE_SANDBOX_MYSQL_ROOT_PASSWORD','CUBE_SANDBOX_MYSQL_PASSWORD','CUBE_SANDBOX_REDIS_PASSWORD','CUBE_SANDBOX_MINIO_ROOT_PASSWORD'):cfg[k]=('e2b_' if k=='CUBE_API_KEY' else '')+secrets.token_hex(24)
for svc in ('mysql','redis','minio'):
 path=data/svc;path.mkdir(parents=True,exist_ok=True);name='comparison-cube-'+svc
 cfg['CUBE_SANDBOX_'+svc.upper()+'_VOLUME']=name
 for vol in (name,'support_'+name):
  sp.run(['docker','volume','create','--driver','local','--opt','type=none','--opt','o=bind','--opt','device='+str(path),'--label','com.docker.compose.project=support','--label','com.docker.compose.volume='+name,vol],check=True)
if not (R/'.env').exists():
 os.umask(0o077);(R/'.env').write_text('\n'.join(k+'='+v for k,v in cfg.items())+'\n')
sp.run(['bash','install.sh','--yes'],cwd=R,check=True)
