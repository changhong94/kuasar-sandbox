import tempfile,os,time,statistics,json,pathlib
rows={}
for name,base in [('loop-xfs','/opt/bench108/data'),('direct-ext4','/opt/bench108/results')]:
 with tempfile.TemporaryDirectory(prefix='tail-sync-',dir=base) as d:
  fd=os.open(d+'/control',os.O_CREAT|os.O_RDWR,0o600);a=[]
  for i in range(10):
   os.pwrite(fd,b'x'*4096,0);t=time.perf_counter_ns();os.fsync(fd);a.append((time.perf_counter_ns()-t)/1e6)
  os.close(fd);rows[name]={'n':10,'median_ms':statistics.median(a),'max_ms':max(a),'samples':a}
p=pathlib.Path('/opt/bench108/results/tail-opt-108/sync-paths.json');p.write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
