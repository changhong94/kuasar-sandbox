from pathlib import Path
import json,subprocess as sp,time,sys
B=Path('/home/hong/src/research/report-review-113')
def run(label,args,**kw):
 stamp=time.time_ns();p=B/'results'/f'{label}-{stamp}.log';t=time.monotonic_ns()
 with p.open('w') as f:r=sp.run(args,stdout=f,stderr=sp.STDOUT,**kw)
 row=dict(label=label,started_unix_ns=stamp,elapsed_ms=(time.monotonic_ns()-t)/1e6,returncode=r.returncode,log=str(p),command=list(map(str,args)))
 with (B/'results/preparation.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 print(json.dumps(row),flush=True)
 if r.returncode:raise RuntimeError(f'{label} failed; see {p}')
 return row
if __name__=='__main__':run(sys.argv[1],sys.argv[2:])
