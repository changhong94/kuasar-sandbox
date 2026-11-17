from pathlib import Path
import subprocess as sp,json,time
R=Path('/home/huawei/src/research/sixway_startup_108');started=time.monotonic()
items=[
('/home/hong/src/kuasar-sandbox/','src/kuasar-off/kuasar-sandbox/'),
('/home/hong/src/private/kuasar-uffd/','src/kuasar-uffd/private/kuasar-uffd/'),
('/home/hong/src/private/kuasar-mlink/','src/kuasar-mlink/private/kuasar-mlink/'),
('/home/hong/src/TencentCloud/CubeSandbox/','src/cube/TencentCloud/CubeSandbox/'),
('/home/hong/src/kvcache-ai/AgentENV/','src/agentenv/kvcache-ai/AgentENV/'),
('/home/hong/src/research/sandbox_fork/kuasar-io/kuasar/','src/kuasar-fork/kuasar-io/kuasar/'),
('/home/hong/src/research/sandbox_fork/cloud-hypervisor/cloud-hypervisor/','src/kuasar-fork/cloud-hypervisor/cloud-hypervisor/'),
('/home/hong/deploy/comparison/','import113/comparison/'),
('/home/hong/deploy/private-pilot/','import113/private-pilot/'),
('/home/hong/deploy/kuasar-oci/','import113/kuasar-oci/'),
('/home/hong/data/comparison/agentenv/deps/','assets/agentenv-deps/'),
('/home/hong/src/research/sandbox_bench/tools/cni/','assets/cni/'),
('/home/hong/data/kuasar-fork/guest/vmlinuz','assets/vmlinuz'),
('/home/hong/data/kuasar-fork/guest/boot.cpio','assets/boot.cpio'),
('/home/hong/src/research/sandbox_fork/tools/oci-pool-10/runtime.ext4','assets/fork-runtime.ext4'),
('/home/hong/src/research/sandbox_fork/tools/generic-pool-10/base.ext4','assets/python-base.ext4'),
('/home/hong/src/research/sandbox_fork/tools/generic-pool-10/base-common.erofs','assets/python-base.erofs'),
('/home/hong/src/research/sandbox_fork/LATEST_FORK.json','assets/LATEST_FORK-113.json')]
for source,target in items:
 dest=R/target
 (dest if target.endswith('/') else dest.parent).mkdir(parents=True,exist_ok=True)
 print('COPY',source,'->',target,flush=True)
 cmd=['rsync','-aSzz','--no-owner','--no-group','--rsync-path=sudo -n rsync','--exclude=target/','--exclude=node_modules/','--exclude=__pycache__/','--exclude=venv/','--exclude=old-state-*/','--exclude=*.sock','--exclude=*.sock.ttrpc','--exclude=*.log','hong@10.213.17.113:'+source,str(dest)+('/' if target.endswith('/') else '')]
 sp.run(cmd,check=True)
(R/'results/transfer.json').write_text(json.dumps(dict(elapsed_s=time.monotonic()-started,items=items),indent=2));print('TRANSFER COMPLETE',flush=True)
