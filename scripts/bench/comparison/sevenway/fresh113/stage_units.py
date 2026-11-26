from pathlib import Path
import json,shutil,subprocess
root=Path('/home/hong/src/research/sevenway-current-20261126')
archive=Path('/home/hong/results/retire-sandbox-services-20261118/systemd')
units=['bench113-layout.service','bench113-dns-egress.service','bench-cube-docker.service','bench-fixture-registry.service','agentenv-comparison.service','kuasar-comparison-node.service','kuasar-comparison-prep.service','bench-private-uffd-prep.service','bench-private-uffd-serve.service','bench-mlink-generic.service','bench-python113-fork.service']
units+=sorted(p.name for p in archive.glob('cube-sandbox-*')if p.is_file())
ledger=[]
for name in units:
 assert subprocess.run(['systemctl','is-active','--quiet',name]).returncode!=0,name
 source=archive/name;target=Path('/run/systemd/system')/name
 if target.exists():
  assert target.read_bytes()==source.read_bytes(),('existing unit differs',str(target))
 else:
  shutil.copy2(source,target);ledger.append(str(target))
 drop=archive/(name+'.d')
 if drop.exists():
  for p in drop.glob('*.conf'):
   t=Path('/run/systemd/system')/(name+'.d')/p.name;t.parent.mkdir(exist_ok=True)
   if t.exists():assert t.read_bytes()==p.read_bytes(),('existing dropin differs',str(t))
   else:shutil.copy2(p,t);ledger.append(str(t))
p=Path('/run/systemd/system/bench-python113-fork.service.d/zzzzz-sevenway-current.conf')
p.write_text('[Service]\nEnvironment=E2B_TEMPLATE_POOL_SIZE=64\nEnvironment=E2B_TEMPLATE_POOL_WORKERS=8\nEnvironment=E2B_TEMPLATE_POOL_REFILL_DELAY_MS=0\n');ledger.append(str(p))
(root/'owned-unit-files.json').write_text(json.dumps(ledger,indent=2))
subprocess.run(['systemctl','daemon-reload'],check=True)
print('STAGED_NOT_STARTED',len(units))
