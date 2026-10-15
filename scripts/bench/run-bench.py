#!/usr/bin/env python3
"""Run the copied bench.py against hong's isolated Alice deployment."""
import argparse,datetime,json,os,pathlib,sys,time,statistics,csv
parser=argparse.ArgumentParser()
parser.add_argument("--samples",type=int,default=3)
parser.add_argument("--warmup",type=int,default=1)
parser.add_argument("--prefetch",choices=["off","memory"],default="memory")
a=parser.parse_args()
if a.samples<1 or a.warmup<0:parser.error("invalid sample count")
state=pathlib.Path('/home/hong/src/.deployment')
c=json.loads((state/'access.json').read_text())
stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
out=state/('bench-smoke-'+stamp);out.mkdir(mode=0o700)
# Permit the deployment user to browse reports; local.env stays root-only (0600).
if os.geteuid() == 0:
 import pwd
 os.chown(out, 0, pwd.getpwnam('hong').pw_gid)
 out.chmod(0o750)
for k in list(os.environ):
 if k.lower() in ('http_proxy','https_proxy','all_proxy'):del os.environ[k]
env={'E2B_DOMAIN':c['domain'],'E2B_API_URL':c['api_url'],'E2B_SANDBOX_URL':c['proxy_url'],'E2B_API_KEY':c['api_key'],'SSL_CERT_FILE':c['ca_file'],'REQUESTS_CA_BUNDLE':c['ca_file'],'NO_PROXY':'*','no_proxy':'*','E2B_NODE_CTL_SOCKET':c['work_dir']+'/node-ctl.socket','E2B_RUN_ROOT':c['run_root']+'/sandboxes','E2B_BIN':c['bin'],'E2B_SAVED_DIR':c['work_dir']+'/saved'}
env["E2B_API_URL"]="https://api."+c["domain"]
import shlex
private=out/'local.env';private.write_text(''.join('export '+k+'='+shlex.quote(v)+'\n' for k,v in env.items()));private.chmod(0o600)
os.environ.update(env);os.environ['E2B_ENV_FILE']=str(private)
bench_dir=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(bench_dir))
import e2b_env
e2b_env.load()
original=e2b_env.api_request
def request(method,path,**kwargs):
 kwargs.setdefault('headers',{})['Host']='api.'+c['domain']
 kwargs.setdefault('timeout',30)
 return original(method,path,**kwargs)
e2b_env.api_request=request
ns={'__name__':'bench_local','__file__':str(bench_dir/'bench.py')}
exec(compile((bench_dir/'bench.py').read_text(),ns['__file__'],'exec'),ns)
def cleanup(sid,namespace=None):
 for _ in range(100):
  if request('GET',f'/sandboxes/{sid}').status_code==404:return []
  time.sleep(.1)
 return ['API deletion not confirmed']
ns['cleanup_sandbox_directories']=cleanup
rows=[]
print('RESULT_DIR:',out,flush=True)
for i in range(a.warmup+a.samples):
 result,failure=ns['run_round'](c['template_id'],'run','echo BENCH_OK; python3 --version','root','/',60,None,a.prefetch,i)
 sample=result['samples'][0] if result['samples'] else None
 row={'index':i,'warmup':i<a.warmup,'prefetch':a.prefetch,'success':failure is None and sample is not None,'sample':sample,'failure':failure}
 rows.append(row)
 with (out/f'samples_{stamp}.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 print(json.dumps(row),flush=True)
 if not row['success']:raise SystemExit('Stopped after failed sample; results retained')
 time.sleep(1)
values=[r['sample']['e2e'] for r in rows if not r['warmup']]
summary={'samples':len(values),'success':len(values),'prefetch':a.prefetch,'concurrency':1,'e2e_ms':{'min':min(values),'median':statistics.median(values),'max':max(values)},'server_launch_timing_available':all(r['sample'].get('create') is not None for r in rows),'scope':'smoke only, not a performance baseline'}
(out/f'summary_{stamp}.json').write_text(json.dumps(summary,indent=2)+'\n')
with (out/f'samples_{stamp}.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['index','warmup','sid','e2e_ms','create_api_ms','warm_ms','server_launch_ms'])
 for r in rows:
  s=r['sample'];w.writerow([r['index'],r['warmup'],s['sid'],s['e2e'],s['create_api'],s['warm'],s.get('create')])
print(json.dumps(summary,indent=2),flush=True)