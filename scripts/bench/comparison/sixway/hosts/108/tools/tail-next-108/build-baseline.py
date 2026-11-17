from pathlib import Path
import shutil,os,subprocess
R=Path('/opt/bench108/results/tail-next-108');K=Path('/opt/bench108/src/kuasar-fork/kuasar-io/kuasar')
shutil.copy('/opt/bench108/deploy/fork/bin/sandboxer',R/'optimized-sandboxer')
q=K/'integrations/e2b';dst=R/'baseline-adapter'
shutil.copytree(q,dst,ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
for name in ['durable_state.py','server.py','template_pool.py','image_pool.py']:
 shutil.copy(R/'before'/name,dst/name)
paths={K/'vmm/sandbox/src/service/snapshot_pool.rs':R/'before/snapshot_pool.rs',K/'vmm/sandbox/src/service/mod.rs':R/'before/service-mod.rs'}
saved={p:p.read_bytes() for p in paths}
env={**os.environ,'PATH':'/home/huawei/src/.tools/cargo/bin:'+os.environ['PATH'],'CARGO_HOME':'/home/huawei/src/.tools/cargo','RUSTUP_HOME':'/home/huawei/src/.tools/rustup','CARGO_TARGET_DIR':'/opt/bench108/build/snapshot-pool'}
try:
 for p,b in paths.items():p.write_bytes(b.read_bytes())
 with (R/'build-baseline.log').open('w') as log:
  subprocess.run(['cargo','+stable','build','--offline','--release','-p','vmm-sandboxer','--bin','cloud_hypervisor'],cwd=K,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 shutil.copy('/opt/bench108/build/snapshot-pool/release/cloud_hypervisor',R/'baseline-sandboxer')
finally:
 for p,data in saved.items():p.write_bytes(data)
 assert all(p.read_bytes()==data for p,data in saved.items())
