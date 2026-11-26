import pathlib,json,subprocess,re,os
base=pathlib.Path('/srv/fork2/data')
def resolve(ref):
 body=ref[len('file://'):];name=body.split('@')[0];m=re.search(r'@location:([^@]+)',body)
 if m:
  loc=m[1];ds=list((base/'publications').glob('*/*/'+loc))
  if not ds:
   ds=[p.parent for p in base.rglob(pathlib.Path(name).name) if loc in str(p)]
  if len(set(ds))!=1:raise RuntimeError('cannot uniquely resolve '+loc+' '+name)
  return ds[0]/name,loc,ds[0]
 p=pathlib.Path(name)
 if p.is_absolute() and p.exists():return p,None,None
 found=list(pathlib.Path('/srv/fork2/bin').glob(name))+list(base.rglob(pathlib.Path(name).name));found=list(dict.fromkeys(found))
 if len(found)!=1:raise RuntimeError('cannot uniquely resolve '+name+' candidates='+str(len(found)))
 return found[0],None,None

def closure_paths(root):
 pid=subprocess.check_output(['systemctl','show','fork2-conductor','-p','MainPID','--value'],text=True).strip()
 service_env=dict(x.split(b'=',1) for x in pathlib.Path('/proc',pid,'environ').read_bytes().split(b'\0') if b'=' in x)
 env=dict(os.environ,MANIFEST_KEY=service_env[b'MANIFEST_KEY'].decode())
 todo=[root];seen=set();paths=set();edges=[]
 while todo:
  ref=todo.pop()
  if ref in seen:continue
  seen.add(ref)
  if not ref.startswith('file://'):raise RuntimeError('nonlocal dependency '+ref)
  path,loc,d=resolve(ref);assert path.is_file();paths.add(str(path))
  if path.suffix not in ('.sandbox','.snapshot'):continue
  cmd=['/srv/fork2/bin/sandbox-ctl','info','--json','--manifest-config','/srv/fork2/manifest.json']
  if loc:cmd+=['--ref-location',loc+'=file://'+str(d)]
  cmd+=[ref if loc else str(path)];p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=30,check=True);cfg=json.loads(p.stdout)
  def walk(v):
   if isinstance(v,str) and v.startswith(('file://','manifest://')):edges.append([ref,v]);todo.append(v)
   elif isinstance(v,dict):
    for x in v.values():walk(x)
   elif isinstance(v,list):
    for x in v:walk(x)
  walk(cfg)
 return [pathlib.Path(p) for p in sorted(paths)]
