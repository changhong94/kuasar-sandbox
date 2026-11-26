import resource_worker181 as a
import pathlib,subprocess as sp,json,time,re
assert a.product=='cube'
if (a.R/'preparation/cube-capacity/configured.json').exists():raise SystemExit(0)
pager=a.Sandbox.list();ids=[]
while pager.has_next:ids.extend(x.sandbox_id for x in pager.next_items())
assert not ids,ids
pid=sp.check_output(['systemctl','show','cube-sandbox-cubelet','-p','MainPID','--value'],text=True).strip()
f=pathlib.Path('/proc/'+pid+'/root/usr/local/services/cubetoolbox/Cubelet/dynamicconf/conf.yaml');s=f.read_text()
root=a.R/'preparation/cube-capacity';root.mkdir(parents=True,exist_ok=True)
backup=root/('before-'+str(time.time_ns())+'.yaml');backup.write_text(s);backup.chmod(0o600)
# Admission quotas, not guest RAM allocation: retain 256 x 2-vCPU/2-GiB guests.
values={'mcpu_limit':'768000','mem_limit':'"768Gi"','mvm_limit':'320','creation_concurrent_num':'256'}
for key,value in values.items():
 s,n=re.subn(r'(?m)^(\s*'+key+r':)\s*.*$',r'\g<1> '+value,s);assert n==1,(key,n)
f.write_text(s)
sp.run(['systemctl','restart','cube-sandbox-cubelet'],check=True)
(root/'configuration-written.json').write_text(json.dumps(dict(values=values,virtual_admission_only=True,physical_memory_kib=int(pathlib.Path('/proc/meminfo').read_text().split('MemTotal:')[1].split()[0]),time=time.time()),indent=2))
# Verify API path and delete this preparation-only instance before measurements.
for attempt in range(30):
 sb=None
 try:
  sb=a.create();assert a.cmd(sb,'echo CAPACITY_READY')=='CAPACITY_READY';break
 except Exception:
  if attempt==29:raise
  time.sleep(1)
 finally:
  if sb:a.b.kill(sb)
(root/'configuration-written.json').replace(root/'configured.json')
print('CUBE_CAPACITY_CONFIGURED')
