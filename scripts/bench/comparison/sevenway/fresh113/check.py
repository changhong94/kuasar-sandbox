#!/usr/bin/env python3
import datetime,fcntl,json,pathlib,subprocess,shlex,sys
root=pathlib.Path(__file__).resolve().parent
with (root/'monitor.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (root/'complete.json').exists():
  subprocess.run(['systemctl','--user','disable','--now','sevenway-current113-monitor.timer'],check=True);raise SystemExit(0)
 code="""import json,pathlib,subprocess,time
r=pathlib.Path('/home/hong/src/research/sevenway-current-20261126');d={'checked_unix':time.time(),'drivers':{}}
for n in ['fork2','six']:
 p=r/n/'status.json';d['drivers'][n]=json.loads(p.read_text()) if p.exists() else {'phase':'missing'}
 d['drivers'][n]['unit']=subprocess.check_output(['systemctl','show','sevenway-current-'+n,'-p','ActiveState','-p','ExecMainStatus'],text=True)
 logs=list((r/n/'logs').glob('*.log'))
 if logs:
  p=max(logs,key=lambda x:x.stat().st_mtime);d['drivers'][n]['latest_log']={'path':str(p),'mtime':p.stat().st_mtime,'tail':p.read_text(errors='replace')[-2000:]}
print(json.dumps(d))
"""
 record={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  q=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','hong@10.213.17.113','sudo -n python3 -c '+shlex.quote(code)],capture_output=True,text=True,timeout=35)
  record['remote']=json.loads(q.stdout) if q.returncode==0 else {'error':q.stderr[-1000:]}
 except Exception as e:record['error']=repr(e)
 (root/'latest-check.json').write_text(json.dumps(record,indent=2))
 if '--probe-only' not in sys.argv:
  message='用户授权每30分钟检查：读取 /home/huawei/codex-work/sevenway-current-113/latest-check.json 和 RUNBOOK.txt，继续113上的20261126七方全新full bench。失败或卡住则保留证据、修复并续跑，确认推进；健康则简短记录结束本次检查。不要重复已成功测试，启动50次、整池20轮、64槽8路准备补槽，保持已记录的镜像和预热口径。七方测试、数据审计、中英文PDF及本次服务清理全部完成后才写complete.json并禁用sevenway-current113-monitor.timer。不动旧fork源码、108/181服务及其他人的任务。'
  q=subprocess.run(['/home/huawei/.local/bin/codex','queue','--thread','01a1d6e0-63d4-7923-8ba7-23e478c23180','--message',message,'--resume'],capture_output=True,text=True,timeout=45)
  record['wake']={'exit_code':q.returncode,'stdout':q.stdout[-1500:],'stderr':q.stderr[-1500:]}
 (root/'latest-check.json').write_text(json.dumps(record,indent=2))
 with (root/'checks.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
 print(json.dumps(record.get('wake',{'probe':True})))
 if record.get('wake',{}).get('exit_code') or 'warning' in record.get('wake',{}).get('stderr','').lower():raise SystemExit(1)
