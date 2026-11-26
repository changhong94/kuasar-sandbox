from pathlib import Path
import time

def capture(sid):
 root=Path('/sys/fs/cgroup/sandbox.slice/sandbox-runner.slice')/('fork2-runner@'+sid+'.service')/'vmm'
 out={'captured_ns':time.time_ns(),'cgroup':str(root)}
 for name in ['cpu.max','cpu.stat','cpu.pressure','memory.events','memory.current','memory.high']:
  try:out[name]=(root/name).read_text()
  except OSError as e:out[name]=str(e)
 try:
  tids=(root/'cgroup.threads').read_text().split();out['threads']={}
  for tid in tids:
   p=Path('/proc')/tid
   try:out['threads'][tid]={'comm':(p/'comm').read_text().strip(),'schedstat':(p/'schedstat').read_text(),'stat':(p/'stat').read_text()}
   except OSError:pass
 except OSError:pass
 return out
