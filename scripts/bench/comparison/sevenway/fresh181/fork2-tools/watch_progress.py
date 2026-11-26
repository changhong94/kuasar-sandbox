import pathlib,json,time,subprocess
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2')
previous=None
while True:
 try:
  status=json.loads((R/'status.json').read_text())
  counts={}
  for mode in ('snapshot-local','snapshot-remote'):
   for lang in ('python','node','ruby'):
    counts[mode+'/'+lang]=len(list((R/'results'/mode/lang).glob('*/[0-9][0-9].json')))
  units={u:subprocess.run(['systemctl','is-active','fork2-sevenway-'+u],capture_output=True,text=True).stdout.strip() for u in ('second','third','fourth')}
  terminal=all(v!='active' for v in units.values())
  state={'phase':status.get('phase'),'counts':counts,'units':units,'attention_required':terminal and status.get('phase')!='tests-finished-report-pending'}
  encoded=json.dumps(state,sort_keys=True)
  latest={**state,'checked_unix':time.time()}
  p=R/'progress-latest.tmp';p.write_text(json.dumps(latest,indent=2));p.replace(R/'progress-latest.json')
  if encoded!=previous:
   with (R/'progress-events.jsonl').open('a') as f:f.write(json.dumps(latest)+'\n')
   previous=encoded
  if terminal:break
 except Exception as e:
  print(type(e).__name__+': '+str(e),flush=True)
 time.sleep(60)
