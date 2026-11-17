import json,pathlib,hashlib,subprocess,shutil
R=pathlib.Path('/opt/bench108/results/snapshot-pool-108');M=pathlib.Path('/opt/bench108');K=M/'src/kuasar-fork/kuasar-io/kuasar';CH=M/'src/kuasar-fork/cloud-hypervisor/cloud-hypervisor'
versions=('baseline','snapshot-v1','snapshot-v2','snapshot-v3','final'); stats={n:json.loads((R/n/'summary.json').read_text()) for n in versions}
p=json.loads((R/'final-phases.json').read_text());t=json.loads((R/'adapter-state.json.snapshot-preparation.json').read_text())['base'];total=json.loads((R/'final-preparation-total.json').read_text());resources=json.loads((R/'final-resources.json').read_text())
text='''108：文件模板快照＋通用资源池

结论：功能路径已实现并通过真实guest验证，但没有获得稳定的启动提速。最终修正后10次中位数95.660ms，慢于本轮原版64.891ms及同轮mlink61.349ms。曾测得53.657ms，但最终重测未复现，不能挑选该组作为交付结论。性能波动根因仍未解决。
因此保留新路径为E2B_SNAPSHOT_POOL=1可选项，当前默认恢复E2B_SNAPSHOT_POOL=0的原有热创建路径；代码与构建产物均保留，没有撤销新功能。默认路径重新创建、执行和销毁的冒烟检查通过。

口径：同一OCI Python镜像 sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79。
应用磁盘仍为同一无压缩EROFS，1vCPU/2048MiB、64槽、补槽等待1000ms。
每个版本每个产品各10次，并发2、五轮交错。各版本原始数据全部保留，没有合并样本或重测后挑最低值。
从创建请求到客户端收到随机shell printf READY，与既有六方口径一致，不包含Python解释器启动。
SDK仍用/bin/bash -l -c，mlink仍用/bin/sh -c。客户端准备、模板准备和预热单列；请求内恢复、第一次缺页、连接/身份重建、命令执行全部计时。
只操作bench108-fork及本任务目录；未修改、重启或终止mlink和其他人的进程。每轮host.json记录系统负载。

完整路径中位数 / 最小 / 最大（ms，每项n=10）：
'''
for n in versions:
 text+=n+'\n'
 for product,d in stats[n].items():text+=f"  {product}: {d['median_ms']:.3f} / {d['min_ms']:.3f} / {d['max_ms']:.3f}\n"
text+='''
实现与版本差异：
1. 每镜像一个不可变文件模板。临时builder挂载、初始化镜像，经过agent屏障和VM暂停保存CPU/设备/RAM；独立保存磁盘文件，完成文件/目录同步后发布manifest，再销毁builder。它不是每镜像保留一池VM。
2. 通用池的64个槽位预备API进程、CNI/namespace/TAP及独立身份，不选择镜像。v1在请求中删除占位VM；v2将该清理移入准备期，Ready槽位不再运行占位guest。
3. 当前没有提前保留KVM/vCPU对象，也没有提前连接到恢复后的guest agent；它们仍在领取时建立。这是与mlink更深入的VMM预备机制之间尚存的差异。
4. 领取先持久化私有分配，再同步恢复文件；改写vsock/serial/TAP配置和NIC快照MAC，使用CopyOnWrite恢复，完成agent检查、熵注入和网络身份重置后再接通网络、持久化发布。失败槽位隔离销毁，不回到Ready。SQLite仍为WAL/EXTRA，未删除安全或持久化屏障。
5. Cloud Hypervisor的RAM文件名是memory-ranges，作用等同memory.img。guest用MAP_PRIVATE共享不可变模板页，写入CoW；不是全量复制RAM。v3把既有fork的每VM halt_poll_ns=0设置扩展到CopyOnWrite文件恢复，未改宿主全局设置。一次53.66ms结果未稳定复现，不能认定它已解决调度/恢复波动。
6. 最终修正临时builder从首个持久化记录起保持私有，制作期间不能通过公开沙箱接口访问；新增回归测试。这不改变热创建算法，最终重新测得95.66ms，之前所有结果仍保留。
7. 显式运行中fork继续原路径，继承当前进程/文件状态，不退回旧模板。
8. 当前模板在adapter启动时重建，无自动缓存淘汰。运行VM和后代可能引用的模板不得删除。新镜像首次使用若未预制，会承担模板准备成本，不会享有热创建耗时。实际guest验证只使用指定Python镜像；两镜像共用池有单元测试，本轮没有新增其它OCI镜像的实机启动结论。

最终请求阶段中位数（ms；各阶段中位数不可直接相加）：
'''
for name,ms in p['phases_ms'].items():text+=f'  {name}: {ms:.3f}\n'
text+=f"  snapshot_bind整体RPC: {p['adapter_ms']['snapshot_bind']:.3f}\n  领取及分配持久化: {p['adapter_ms']['pool_lease']:.3f}\n  首次命令到客户端收到: {p['first_command_client_ms']:.3f}\n"
text+='集中开销是KVM/设备恢复、agent连接和guest身份重置。模板路径确实消除了领取时的挂载/预取RPC，但这些替代开销更高且波动大；不能说已经找到了波动的最终根因。\n'
text+=f'''
最终版准备/预热/补槽成本（不计作免费）：
- 服务启动到API监听：{total['service_start_to_api_listen_ms']:.3f} ms。
- 通用64槽准备：{p['pool_startup']['elapsed_ms']:.3f} ms。
- 本镜像模板制作：{t['preparation_ms']:.3f} ms，含builder启动、挂载和快照持久化。
- 2GiB内存文件预热：{t['warmup_ms']:.3f} ms。
- builder创建至预热、销毁、CNI清理和状态提交全部完成：{total['total_builder_prepare_warm_cleanup_ms']:.3f} ms（包含上两项，不重复累加）。
- 正式10次对应补槽工作中位数：{p['refill']['elapsed_ms']:.3f} ms。
- 从销毁到替代槽Ready中位数：{p['refill']['replacement_ms']:.3f} ms，包含1000ms等待及排队。
- 这组未耗尽池，misses=0；不代表持续超过补槽吞吐时也能保持相同耗时。

资源：
- 模板路径64个空资源槽、seed与控制进程的PSS合计{resources['totals']['Pss']/1024:.1f} MiB，FD {resources['totals']['fds']}个。
- 每镜像模板RAM文件2GiB，预热占用共享host页缓存，未包含在上述空槽进程PSS中。
- 模板磁盘逻辑256MiB+16GiB，分配块约170MiB，包含reflink共享块，不等于独占物理占用。旧实验模板保留为研究产物，磁盘总占用不等于单模板占用。
- v1运行占位guest的池约858MiB PSS/11775FD；最终空资源池约363MiB/2111FD。当前默认恢复原运行通用池，不能将模板池资源指标冒充当前默认服务指标。

验证结果：
- 59项Python测试通过，无skip；涵盖私有builder、私有绑定、失败隔离、不提前发布、通用池、OCI和真实reflink。
- KVM halt polling测试通过，确认宿主全局配置不变。
- 真实Linux guest中，Python进程PID/nonce、16MiB内存状态跨运行中fork继承；父写20、子写30独立，抽样376页仍共享PFN。
- 父先删除、子先删除、父删除后子再fork孙代均通过。
- 两个模板恢复实例映射同一RAM文件且均为rw-p；MAC、IP、CID不同，双向HTTP收到各自随机标识，删除一个后另一个继续服务。
- 最终10次创建、READY和销毁全部成功；结束时64 Ready、0 Assigned。功能通过不等于性能目标通过。

复现：
脚本 /opt/bench108/tools/snapshot-pool-108/，原始结果在本目录各版本子目录。
启用模板路径：为本任务bench108-fork服务设置E2B_SNAPSHOT_POOL=1，保留KUASAR_SNAPSHOT_POOL_ROOT，确认无已分配沙箱后排空并重启；不要修改其它产品服务。
默认E2B_SNAPSHOT_POOL=0；default-smoke.json记录回到原路径后的创建/执行/销毁检查。
代码：Kuasar integrations/e2b/image_pool.py、vm_backend.py、test_snapshot_pool.py、test_vm_backend.py、README.md；vmm/sandbox/src/service/snapshot_pool.rs和路由；Cloud Hypervisor vmm/src/vm.rs。未提交commit。
'''
(R/'REPORT.txt').write_text(text)
meta={'default_snapshot_pool':False,'experimental_snapshot_pool':True,'result':stats['final'],'report':str(R/'REPORT.txt')}
for name,root in [('kuasar',K),('cloud-hypervisor',CH)]:meta[name]={'branch':subprocess.check_output(['git','-C',str(root),'branch','--show-current'],text=True).strip(),'head':subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()}
for name in ('cloud-hypervisor','sandboxer','image-mount'):
 f=M/'deploy/fork/bin'/name;meta[name+'-binary']={'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
meta['image']=json.loads((R/'images.json').read_text());(R/'manifest.json').write_text(json.dumps(meta,indent=2))
S=R/'sources'
for root,names in [(K,['integrations/e2b/image_pool.py','integrations/e2b/vm_backend.py','integrations/e2b/test_snapshot_pool.py','integrations/e2b/test_vm_backend.py','integrations/e2b/README.md','vmm/sandbox/src/service/snapshot_pool.rs','vmm/sandbox/src/service/mod.rs','vmm/sandbox/src/cloud_hypervisor/live_fork.rs','vmm/sandbox/src/cloud_hypervisor/mod.rs']),(CH,['vmm/src/vm.rs'])]:
 for name in names:
  dest=S/root.name/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,dest)
print(R/'REPORT.txt')
