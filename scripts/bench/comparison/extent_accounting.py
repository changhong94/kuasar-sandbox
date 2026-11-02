import os,stat,struct,fcntl
from pathlib import Path
HEADER=struct.Struct('=QQIIII')
EXTENT=struct.Struct('=QQQQQIIII')
def union_size(ranges):
 total=0;end=0
 for a,b in sorted(ranges):
  if b>end:total+=b-max(a,end);end=b
 return total
def scan(paths):
 if len({os.stat(path).st_dev for path in paths}) != 1:
  raise ValueError('Physical extent unions require paths on one filesystem')
 ranges=[];seen=set();files=0;allocated=0;shared=0;flags={}
 for root in paths:
  device=os.stat(root).st_dev
  for directory,dirs,names in os.walk(root,followlinks=False):
   dirs[:]=[d for d in dirs if not os.path.islink(os.path.join(directory,d)) and os.stat(os.path.join(directory,d)).st_dev==device]
   for name in names:
    p=os.path.join(directory,name);s=os.lstat(p)
    if not stat.S_ISREG(s.st_mode) or (s.st_dev,s.st_ino) in seen:continue
    assert s.st_dev==device
    seen.add((s.st_dev,s.st_ino));files+=1;allocated+=s.st_blocks*512
    with open(p,'rb',buffering=0) as f:
     start=0
     while True:
      n=256;buf=bytearray(HEADER.size+n*EXTENT.size)
      HEADER.pack_into(buf,0,start,(1<<64)-1-start,1,0,n,0)
      fcntl.ioctl(f.fileno(),0xC020660B,buf,True)
      count=HEADER.unpack_from(buf)[3]
      if not count:break
      last=0
      for i in range(count):
       logical,physical,length,_,_,flag,*_=EXTENT.unpack_from(buf,HEADER.size+i*EXTENT.size)
       assert not flag & (2|4|256|512|1024), (p,hex(flag))
       flags[str(flag)]=flags.get(str(flag),0)+1
       ranges.append((physical,physical+length))
       if flag&8192:shared+=length
       start=logical+length;last=flag
      if last&1:break
 return dict(unique_extent_bytes=union_size(ranges),file_allocated_bytes=allocated,file_count=files,extent_count=len(ranges),shared_extent_bytes_with_duplicates=shared,flags=flags)
if __name__=='__main__':
 import json,sys
 print(json.dumps(scan(sys.argv[1:]),indent=2))
