from pathlib import Path
import shutil,subprocess,json
r=Path('/home/hong/src/research/startup-latest-20261126');old=Path('/home/hong/src/research/sevenway-fresh-20261124/fork2');(r/'tools').mkdir(exist_ok=True);(r/'results').mkdir(exist_ok=True)
for n in ['startup.py','languages.py','cache_state.py']:
 s=(old/'tools'/n).read_text().replace(str(old),str(r));(r/'tools'/n).write_text(s)
shutil.copy2(old/'results/template-backings.json',r/'results/template-backings.json')
(r/'tools/run.py').write_text('''import subprocess,json,pathlib,fcntl
r=pathlib.Path('/home/hong/src/research/startup-latest-20261126')
lock=open('/run/skyrl-threeway-benchmark.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
p=subprocess.Popen(['/srv/fork2/bin/python-sdk','-u',str(r/'tools/startup.py'),'fork2'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
assert json.loads(p.stdout.readline())['ready']
for i in range(51):
 p.stdin.write(json.dumps(['python',i])+'\\n');p.stdin.flush();line=p.stdout.readline();assert line,p.poll();v=json.loads(line);print(json.dumps(v),flush=True);assert v['success'] and v['destroyed'] and not v.get('pool_error')
p.stdin.write('null\\n');p.stdin.flush();assert p.wait(timeout=60)==0
''')
