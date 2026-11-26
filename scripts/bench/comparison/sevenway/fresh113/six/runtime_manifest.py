"""Hash binaries of dedicated product processes; no command lines or credentials."""
from pathlib import Path
import hashlib,json,os,sys,time
B=Path('/home/hong/src/research/sevenway-current-20261126/six');sys.path.insert(0,str(B/'tools'))
import runner as r
out={'observed_unix':time.time(),'scope':'Dedicated product process executables after functional/benchmark batches; no process arguments or environment collected','products':{}}
cache={}
for product in r.prods:
 r.pr=product;r.setup(product);data=r.resources();exes={}
 for pid in data['processes']:
  path=Path('/proc')/str(pid)/'exe'
  try:
   name=os.readlink(path)
   stat=path.stat();key=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)
   if key not in cache:
    h=hashlib.sha256()
    with path.open('rb') as stream:
     while chunk:=stream.read(1048576):h.update(chunk)
    cache[key]=h.hexdigest()
   exes[name]={'sha256':cache[key],'bytes':stat.st_size}
  except (FileNotFoundError,ProcessLookupError):continue
 out['products'][product]=exes
assert all(out['products'].values())
(B/'runtime-binary-manifest.json').write_text(json.dumps(out,indent=2))
