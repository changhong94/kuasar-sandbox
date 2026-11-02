"""Fixed workload bytes; no model invocation, network downloads or scoring edits."""
CPU = r'''
import hashlib,json,time,resource
b=hashlib.shake_256(b'perf-cpu-v1').digest(1024*1024)
t=time.perf_counter();c=time.process_time();h=hashlib.sha256()
for i in range(256): h.update(b)
print(json.dumps(dict(kind='sha256-256MiB',wall_ms=(time.perf_counter()-t)*1000,cpu_ms=(time.process_time()-c)*1000,sha256=h.hexdigest(),maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))
'''

MEMORY = r'''
import mmap,hashlib,json,time,resource,gc,os
def mark(stage,**kw):
    with open('/tmp/perf-memory-events.jsonl','a') as f:
        f.write(json.dumps(dict(stage=stage,time=time.time(),rss_status=open('/proc/self/status').read(),**kw))+'\n')
size=128*1024*1024
mark('before');time.sleep(2)
b=mmap.mmap(-1,size);block=hashlib.shake_256(b'perf-memory-v1').digest(1024*1024)
t=time.perf_counter()
for off in range(0,size,len(block)): b[off:off+len(block)]=block
digest=hashlib.sha256(b).hexdigest()
mark('allocated_and_written',size=size,sha256=digest,write_ms=(time.perf_counter()-t)*1000)
time.sleep(3)
b.close();del b,block;gc.collect();mark('unmapped')
time.sleep(5);mark('after_5s');time.sleep(10);mark('after_15s')
print(open('/tmp/perf-memory-events.jsonl').read())
'''

IO = r'''
import hashlib,os,time,json
path='/tmp/perf-io.bin';size=32*1024*1024
block=hashlib.shake_256(b'perf-io-v1').digest(1024*1024)
t=time.perf_counter()
with open(path,'wb') as f:
    for _ in range(size//len(block)): f.write(block)
    f.flush();os.fsync(f.fileno())
write=(time.perf_counter()-t)*1000
rows=[]
for mode in ('file-advised-cold','warm'):
    with open(path,'rb') as f:
        if mode=='file-advised-cold': os.posix_fadvise(f.fileno(),0,0,os.POSIX_FADV_DONTNEED)
        t=time.perf_counter();h=hashlib.sha256()
        while True:
            x=f.read(1024*1024)
            if not x: break
            h.update(x)
    rows.append(dict(mode=mode,ms=(time.perf_counter()-t)*1000,sha256=h.hexdigest()))
assert rows[0]['sha256']==rows[1]['sha256']
print(json.dumps(dict(size=size,write_fsync_ms=write,reads=rows,scope='Guest file cache advice only; host/application/device caches not evicted')))
'''

STORAGE = r'''
import hashlib,os,json,sys
mode=sys.argv[1];seed=sys.argv[2];root='/tmp/perf-storage';os.makedirs(root,exist_ok=True)
paths=[]
for entropy in ('low','high'):
    p=root+'/'+entropy+'.bin';h=hashlib.sha256()
    with open(p,'wb') as f:
        for i in range(32):
            b=(hashlib.sha256(('low:'+seed).encode()).digest()*(1024*1024//32)) if entropy=='low' else hashlib.shake_256(('perf-storage-v1:'+seed+':'+str(i)).encode()).digest(1024*1024)
            f.write(b);h.update(b)
        f.flush();os.fsync(f.fileno())
    s=os.stat(p);paths.append(dict(path=p,sha256=h.hexdigest(),logical_bytes=s.st_size,allocated_bytes=s.st_blocks*512,entropy=entropy))
print(json.dumps(dict(mode=mode,seed=seed,files=paths)))
'''

# A bounded, identical useful action for sustained creation tests; output checked.
PRESSURE = "python3 -c 'import hashlib; print(hashlib.sha256(b\"paired-pressure-v1\"*65536).hexdigest())'"
