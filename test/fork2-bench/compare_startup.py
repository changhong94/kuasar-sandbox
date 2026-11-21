#!/usr/bin/env python3
import subprocess,sys,pathlib,json,statistics
out=pathlib.Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
script=str(pathlib.Path(__file__).with_name('compare_worker.py'));python='/opt/bench108/venv/bin/python';ps={};rows=[]
try:
 for k in ['old','new']:
  cmd=(['ip','netns','exec','forkcmp-old'] if k=='old' else [])+[python,script,k]
  ps[k]=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=(out/(k+'.stderr')).open('w'),text=True,bufsize=1)
  assert json.loads(ps[k].stdout.readline())['ready']
 for i in range(11):
  for k in (['old','new'] if i%2==0 else ['new','old']):
   p=ps[k];p.stdin.write(json.dumps({'iteration':i})+'\n');p.stdin.flush();r=json.loads(p.stdout.readline());rows.append(r)
   (out/'samples.json').write_text(json.dumps(rows,indent=2));print(json.dumps(r),flush=True)
   assert r['success'] and r.get('deleted'),r
 summary={k:{m:{'median':statistics.median(v:=[r[m] for r in rows if r['product']==k and not r['warmup']]),'max':max(v)} for m in ['api_ms','print_ms','second_python_ms']} for k in ps}
 (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
finally:
 for p in ps.values():
  if p.poll() is None:p.stdin.write('null\n');p.stdin.flush();p.wait(timeout=90)
