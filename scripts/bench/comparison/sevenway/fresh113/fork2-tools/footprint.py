"""Product PSS + resident owned data-file cache, subtract shared mapped pages once.
Only dedicated product data roots are included; host-wide caches are not charged.
PFN flags exclude private CoW anonymous pages from the overlap subtraction.
"""
import pathlib,os,re,ctypes,struct,json
libc=ctypes.CDLL(None,use_errno=True);libc.mmap.restype=ctypes.c_void_p;libc.mmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_long];libc.mincore.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p];libc.munmap.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
PAGE=4096

def measure(product,extra):
 roots=['/srv/fork2/data/','/run/fork2/','/home/hong/src/research/fork2-control-persistent/']if product=='fork2'else ['/home/hong/src/research/fork2-print-compare-113/old/data/','/home/hong/src/research/fork2-print-compare-113/old/control/','/run/print113-old/']
 pattern=re.compile(r'/fork2-(?:runner@|shared-controller\.|conductor\.|proxy\.|switch\.|store\.)'if product=='fork2'else r'/fork2-old-print-(?:compare|store)\.service')
 pids=[];files={};maps=[];pss=0;errors=[]
 def add(path,label=None):
  try:
   st=os.stat(path)
   import stat
   if not stat.S_ISREG(st.st_mode):return
   key=(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino)
   files.setdefault(key,dict(path=str(path),label=label or str(path),size=st.st_size,allocated=st.st_blocks*512))
  except OSError as e:errors.append(str(e))
 for proc in pathlib.Path('/proc').glob('[0-9]*'):
  matched=False
  try:
   if not pattern.search((proc/'cgroup').read_text()):continue
   matched=True
   stat=(proc/'stat').read_text().rsplit(')',1)[1].split()
   if int(stat[6])&0x00200000:continue
   pids.append(proc.name)
   vals={l.split(':')[0]:int(l.split()[1])for l in (proc/'smaps_rollup').read_text().splitlines()if l.startswith(('Pss:','Pss_Anon:'))};pss+=vals['Pss']*1024
   for fd in (proc/'fd').iterdir():
    try:
     label=os.readlink(fd)
     if any(label.startswith(r)for r in roots):add(fd,label)
    except FileNotFoundError:pass
   for line in (proc/'maps').read_text().splitlines():
    x=line.split(None,5)
    if len(x)<6 or not any(x[5].startswith(r)for r in roots):continue
    a,b=(int(n,16)for n in x[0].split('-'));major,minor=(int(n,16)for n in x[3].split(':'));key=(major,minor,int(x[4]));maps.append((proc.name,a,b,key))
    path=x[5].removesuffix(' (deleted)')
    if pathlib.Path(path).exists():add(path)
  except (FileNotFoundError,ProcessLookupError):
   if matched:errors.append('process changed '+proc.name)
 for path in extra:add(path)
 present=set()
 for pid,a,b,key in maps:
  if key not in files:continue
  with open('/proc/'+pid+'/pagemap','rb',buffering=0)as f:
   f.seek(a//PAGE*8);raw=f.read((b-a)//PAGE*8)
  for (v,)in struct.iter_unpack('Q',raw):
   if v>>63:present.add(v&((1<<55)-1))
 assert 0 not in present,'PFNs unavailable; cannot claim deduplicated totals'
 overlap=0;flagsfd=os.open('/proc/kpageflags',os.O_RDONLY)
 try:
  ordered=sorted(present);i=0
  while i<len(ordered):
   lo=ordered[i];j=i+1
   while j<len(ordered)and ordered[j]-lo<8192:j+=1
   raw=os.pread(flagsfd,(ordered[j-1]-lo+1)*8,lo*8)
   for pfn in ordered[i:j]:
    flags=struct.unpack_from('Q',raw,(pfn-lo)*8)[0]
    if not flags&((1<<12)|(1<<24)):overlap+=PAGE
   i=j
 finally:os.close(flagsfd)
 rows=[]
 for key,v in files.items():
  if not v['size']:continue
  fd=os.open(v['path'],os.O_RDONLY)
  try:
   size=v['size'];pages=(size+PAGE-1)//PAGE;p=libc.mmap(None,size,0,1,fd,0)
   if p==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_errno(),'mmap')
   try:
    vec=(ctypes.c_ubyte*pages)();assert libc.mincore(p,size,vec)==0;resident=bytes(vec).translate(bytes(i&1 for i in range(256))).count(1)*PAGE
   finally:libc.munmap(p,size)
   rows.append(dict(identity=key,path=v['label'],allocated_bytes=v['allocated'],resident_bytes=resident))
  finally:os.close(fd)
 cache=sum(r['resident_bytes']for r in rows);assert overlap<=cache,(overlap,cache)
 assert not errors,errors
 return dict(process_pss_mib=pss/2**20,owned_file_cache_mib=cache/2**20,mapped_file_overlap_mib=overlap/2**20,total_deduplicated_mib=(pss+cache-overlap)/2**20,files=rows,pids=pids,scope='all product process PSS plus resident named templates and open/mapped files under dedicated data/runtime roots; mapped file PFNs subtracted once; excludes unrelated files and kernel memory')
