"""Warm allocated source extents only; never populate sparse zero holes."""
import ctypes,os,time,errno
libc=ctypes.CDLL(None,use_errno=True);libc.mmap.restype=ctypes.c_void_p
libc.mmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_long]
libc.mincore.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p];libc.munmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
PAGE=os.sysconf('SC_PAGE_SIZE')
def extents(fd,size):
 out=[];off=0
 while off<size:
  try:start=os.lseek(fd,off,os.SEEK_DATA)
  except OSError as e:
   if e.errno==errno.ENXIO:break
   raise
  end=min(size,os.lseek(fd,start,os.SEEK_HOLE));assert end>start;out.append((start,end));off=end
 return out

def residency(path):
 fd=os.open(path,os.O_RDONLY)
 try:
  st=os.fstat(fd);size=st.st_size;pages=(size+PAGE-1)//PAGE;runs=extents(fd,size);bits=b''
  if size:
   ptr=libc.mmap(None,size,0,1,fd,0);assert ptr!=ctypes.c_void_p(-1).value
   try:
    vec=(ctypes.c_ubyte*pages)();assert libc.mincore(ptr,size,vec)==0;bits=bytes(v&1 for v in vec)
   finally:libc.munmap(ptr,size)
  data_pages=sum((b+PAGE-1)//PAGE-a//PAGE for a,b in runs)
  resident_data=sum(sum(bits[a//PAGE:(b+PAGE-1)//PAGE])for a,b in runs)
  return dict(path=str(path),logical_bytes=size,allocated_bytes=st.st_blocks*512,pages=pages,resident_pages=sum(bits),data_pages=data_pages,resident_data_pages=resident_data)
 finally:os.close(fd)

def warm_once(paths):
 start=time.perf_counter_ns();before=[residency(p)for p in paths]
 for p,row in zip(paths,before):
  if row['data_pages']==row['resident_data_pages']:continue
  fd=os.open(p,os.O_RDONLY)
  try:
   for a,b in extents(fd,os.fstat(fd).st_size):
    while a<b:
     part=os.pread(fd,min(4<<20,b-a),a);assert part;a+=len(part)
  finally:os.close(fd)
 after=[residency(p)for p in paths];assert all(v['data_pages']==v['resident_data_pages']for v in after)
 return dict(mode='local_warm',method='allocated immutable extents resident; no sparse-hole reads',before=before,after=after,verified=True,preparation_ms=(time.perf_counter_ns()-start)/1e6)

def verified_warm(paths):
 start=time.perf_counter_ns()
 for attempt in range(3):
  try:
   proof=warm_once(paths);proof["warm_attempts"]=attempt+1;proof["preparation_ms"]=(time.perf_counter_ns()-start)/1e6;return proof
  except AssertionError:
   if attempt==2:raise

def condition(paths,mode):
 import time
 if mode=='local_warm':return verified_warm(paths)
 assert mode=='local_cold'
 t=time.monotonic_ns()
 for attempt in range(5):
  for p in paths:
   fd=os.open(p,os.O_RDONLY)
   try:os.fsync(fd);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED)
   finally:os.close(fd)
  rows=[residency(p) for p in paths]
  data=sum(x['data_pages'] for x in rows);resident=sum(x['resident_data_pages']for x in rows)
  if resident<=max(1,data*.01):return dict(mode=mode,preparation_ms=(time.monotonic_ns()-t)/1e6,files=rows,data_pages=data,resident_data_pages=resident,verified=True,sparse_holes_excluded=True)
  time.sleep(.05)
 raise RuntimeError(('target data cache remains resident',rows))
