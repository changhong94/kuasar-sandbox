import os,sys,stat,hashlib,json
from pathlib import Path
root=Path(sys.argv[1]);out={}
for directory,dirs,files in os.walk(root):
 for name in dirs+files:
  p=Path(directory)/name;st=p.lstat();entry={'mode':st.st_mode,'uid':st.st_uid,'gid':st.st_gid,'mtime_ns':st.st_mtime_ns}
  if stat.S_ISREG(st.st_mode):
   with p.open('rb') as f: entry['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
  elif stat.S_ISLNK(st.st_mode):entry['target']=os.readlink(p)
  elif stat.S_ISCHR(st.st_mode) or stat.S_ISBLK(st.st_mode):entry['rdev']=st.st_rdev
  entry['xattrs']={k:os.getxattr(p,k,follow_symlinks=False).hex() for k in os.listxattr(p,follow_symlinks=False)}
  out[str(p.relative_to(root))]=entry
Path(sys.argv[2]).write_text(json.dumps(out,sort_keys=True))
