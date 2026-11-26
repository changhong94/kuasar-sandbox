import pathlib,subprocess,json
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181/fork2');T=R/'tools';P='/srv/fork2/bin/python-sdk'
def status(s):print(s,flush=True)
status('three-language-image-startup')
p=subprocess.Popen([P,'-u',str(T/'startup.py'),'fork2'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert json.loads(p.stdout.readline())['ready']
for lang in ['python','node','ruby']:
 for i in range(51):
  p.stdin.write(json.dumps([lang,i])+'\n');p.stdin.flush();line=p.stdout.readline();assert line, p.poll();v=json.loads(line);print(v,flush=True);assert v['success']and v['destroyed']and not v.get('pool_error')
p.stdin.write('null\n');p.stdin.flush();assert p.wait(timeout=60)==0
