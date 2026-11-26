from pathlib import Path
import json,collections,shlex
B=Path('/home/hong/src/research/sevenway-current-20261126/six');out={}
for interval in [0,10,25,50,100]:
 out[str(interval)]={}
 for p in ['kuasar-fork','kuasar-mlink','agentenv','cube','kuasar-off','kuasar-uffd']:
  r=json.loads((B/f'results/paced/{interval}/{p}/result.json').read_text());terminal={};phases=collections.defaultdict(list)
  ids=[x['sandbox_id'] for x in r['requests'] if x.get('api_success')]
  assert len(ids)==len(set(ids))==r['api']['completed']
  assert {x['sandbox_id'] for x in r['requests'] if x['success']}<=set(r['retained_alive_before_cleanup'])
  log=B/f'preparation/{interval}/{p}/server/orch.log'
  if log.exists():
   for line in log.read_text().splitlines():
    try:f=dict(v.split('=',1) for v in shlex.split(line) if '=' in v)
    except ValueError:continue
    if f.get('msg')=='sandbox launch terminal':terminal[f['sid']]=f
    if f.get('msg')=='sandbox launch phase':phases[f['sid']].append(f)
  cube_findings=collections.defaultdict(list)
  cube_log=B/f'preparation/{interval}/{p}/server/cubemaster-req.log'
  if cube_log.exists():
   for line in cube_log.read_text().splitlines():
    try:item=json.loads(line)
    except ValueError:continue
    content=item.get('LogContent','')
    if 'quotaCpuFree:' in content or 'quotaMemFree:' in content or 'CpuUtil:' in content:
     cube_findings[item.get('RequestId','')].append(content)
  counts=collections.Counter();evidence=[]
  for req in r['requests']:
   if req['success']:continue
   sid=req.get('sandbox_id');t=terminal.get(sid)
   if t and t.get('result')=='failure':
    key=t.get('failure_stage','unknown')+': '+t.get('err','unknown')
    if t.get('failure_stage')=='artifact_prepare' and any(x.get('phase')=='runner_wait_duration' and x.get('duration','').startswith('5.') for x in phases[sid]):key='runner_assignment_5s_timeout'
    evidence.append({'index':req['index'],'sid':sid,'terminal':t,'phases':phases[sid]})
   elif p=='cube' and 'no more resource' in req.get('error',''):key='cubemaster_no_resource'
   elif '429' in req.get('error',''):key='http_429_rate_limit'
   else:key='unresolved: '+req.get('error_type','unknown')+': '+req.get('error','')[:180]
   counts[key]+=1
  out[str(interval)][p]={'failed':r['failed_requests'],'causes':dict(counts),'server_evidence':evidence,'retention_failed':len(r['retention_failed'])}
  assert sum(counts.values())==r['failed_requests']
rows=[]
labels={
 'runner_assignment_5s_timeout':('artifact_prepare：等待 runner 分配达到 5 秒内部超时','artifact_prepare: runner assignment reached the internal 5 s deadline'),
 'cubemaster_no_resource':('CubeMaster 资源准入拒绝；具体限制项见原始服务日志','CubeMaster resource admission refusal; detailed filter evidence retained'),
 'http_429_rate_limit':('HTTP 429 限流','HTTP 429 rate limit')}
for interval,products in out.items():
 for p,item in products.items():
  r=json.loads((B/f'results/paced/{interval}/{p}/result.json').read_text())
  rows.append({'interval_ms':int(interval),'product':p,'success':r['print']['completed'],'failed':r['failed_requests'],'alive':len(r['retained_alive_before_cleanup']),'retention_failed':len(r['retention_failed']),'remaining':len(r['public_remaining']),'reasons':[{'key':k,'cn':labels.get(k,(k,k))[0],'en':labels.get(k,(k,k))[1],'count':v} for k,v in item['causes'].items()],'evidence':item['server_evidence']})
(B/'failure-analysis.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False))
print(json.dumps({i:{p:v['causes'] for p,v in a.items()} for i,a in out.items()},indent=2))
