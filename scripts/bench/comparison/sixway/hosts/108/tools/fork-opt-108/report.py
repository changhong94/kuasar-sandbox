from pathlib import Path
import json,statistics,hashlib,difflib,shutil,subprocess as sp
M=Path('/opt/bench108');R=M/'results/fork-opt-108';Q=M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'
s=json.loads((R/'stages.json').read_text());before=s['baseline']['end_to_end'];after=s['after']['end_to_end'];b=s['baseline']['median_ms'];a=s['after']['median_ms'];validation=json.loads((R/'validation.json').read_text());assert validation['success']
loads={}
for variant in ['baseline','after']:
 rows=[json.loads(p.read_text()) for p in (R/variant).glob('[0-9]*.json')];assert len(rows)==20 and all(x['success'] and x['destroyed'] for x in rows)
 xs=sorted([json.loads(p.read_text()) for p in (R/variant).glob('*-host.json')],key=lambda x:x['time_ns']);cpu=[]
 for x,y in zip(xs,xs[1:]):
  u=list(map(int,x['stat'].splitlines()[0].split()[1:9]));v=list(map(int,y['stat'].splitlines()[0].split()[1:9]));d=[n-m for m,n in zip(u,v)];cpu.append(100*(1-(d[3]+d[4])/sum(d)))
 loads[variant]={'mean_cpu_busy_percent':statistics.mean(cpu),'first_loadavg':xs[0]['loadavg'],'last_loadavg':xs[-1]['loadavg']}
changes=[]
for name in ['image_pool.py','template_pool.py','server.py']:
 changes.extend(difflib.unified_diff((R/name).read_text().splitlines(True),(Q/name).read_text().splitlines(True),fromfile='before/'+name,tofile='after/'+name))
(R/'changes.patch').write_text(''.join(changes));(R/'source').mkdir(exist_ok=True)
for name in ['image_pool.py','template_pool.py','image-mount.c','test_image_pool.py','durable_state.py','README.md']:shutil.copy2(Q/name,R/'source'/name)
shutil.copy2(M/'deploy/fork/supervisor.py',R/'supervisor-after.py');shutil.copy2(M/'deploy/fork/mount-helper-preparation.json',R/'mount-helper-preparation.json')
for n in ['kuasar-fork','kuasar-mlink']:shutil.copy2(M/'results'/('audit-'+n+'.json'),R/('audit-'+n+'.json'))
sha={}
for p in [Q/'image-mount.c',M/'deploy/fork/bin/image-mount',M/'assets/python-base.ext4',M/'deploy/fork/bin/cloud-hypervisor',M/'deploy/fork/bin/sandboxer']:
 with p.open('rb') as f:sha[str(p)]=hashlib.file_digest(f,'sha256').hexdigest()
noimg=list((M/'data/fork').rglob('memory.img'));assert not noimg
manifest={'load':loads,'sha256':sha,'fork_memory_img_files':[],'ksm_run':Path('/sys/kernel/mm/ksm/run').read_text().strip(),'tests':'42 passed, no skips (tests-root.log)','helper_preparation':json.loads((R/'mount-helper-preparation.json').read_text())}
(R/'manifest.json').write_text(json.dumps(manifest,indent=2))
lines=['108 池化 fork：阶段定位与优化','', '同一固定基础镜像 sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79。', '同一 SDK/CLI 入口：请求开始到客户端收到随机 shell printf READY；不包含 Python 解释器启动。', '复用客户端与两个持久工作线程；每个版本、每个产品 10 次，并发 2，五轮交错。', '64 槽、1000 ms 补槽等待等配置保持一致；只有本次研究所属 fork 服务被重建，其他人的进程未操作。', '', '此前 111.669 ms 来自上一轮迁移结果；本轮同负载复测用于优化前后对比。', '产品                   本轮优化前中位数 ms    优化后中位数 ms']
for n in ['kuasar-fork','kuasar-mlink']:lines.append(f'{n:22s} {before[n]["median_ms"]:18.3f} {after[n]["median_ms"]:18.3f}')
lines+=['',f'fork 降低 {(1-after["kuasar-fork"]["median_ms"]/before["kuasar-fork"]["median_ms"])*100:.1f}%；仍未追平 mlink。','', 'fork 阶段中位数（ms）：各阶段中位数不能直接相加；包含阶段之间的锁/调度等待。','阶段                     优化前        优化后']
for label,k in [('领取槽位（含持久化）','pool_lease'),('单独镜像绑定意图提交','image_intent'),('sandbox-get RPC','admin_get'),('设备添加 API','image_disk_attach'),('guest 镜像挂载 RPC','image_mount'),('挂载后持久发布','image_publish'),('服务端整个镜像绑定','image_bind_total'),('客户端创建 API','create_api'),('首次命令到客户端收到','first_command_client'),('其中执行 RPC','execute_rpc'),('其中 guest 执行','exec_guest'),('端到端','total')]:lines.append(f'{label:24s} {b.get(k,0):10.3f} {a.get(k,0):10.3f}')
lines += ['', '定位结论：', '1. 111.7 ms 不是 VM fork 的暂停时间。预备 VM 已经存在，领取时仍需绑定镜像、热插拔设备、挂载 ext4/overlay、持久发布，再执行命令。', '2. SDK/RPC 外层不是主要瓶颈：本轮创建 API 超出服务端镜像绑定的中位数为优化前 3.731 ms、优化后 5.863 ms；首次命令 RPC 外约 1–2 ms。', '3. mlink 对照使用预先捕获的 Full 模板及 full-memory/storage 预热；镜像相关 guest 状态在模板准备阶段已有。fork 通用池在领取时才把应用镜像接入 guest，因此还有额外的热插拔与文件系统工作。', '4. 首次命令 guest 执行仍约 17.5 ms。E2B SDK 使用 /bin/bash -l -c；mlink 原测试使用 /bin/sh -c。保持原计时入口，未以改 shell 或省略登录配置降低数字。', '', '实施：', '  领取槽位和镜像标识合并为同一 durable private-binding 提交，删去重复提交；VM 修改仍在该提交成功后进行。', '  镜像挂载使用单个静态 guest helper，减少多次工具进程启动；依然在领取请求内完成，仍是同一个通用 VM 池。', '  热插拔等待检查 open + BLKGETSIZE64；仅检查 /dev/vdb 存在会遭遇 ENXIO，已在真实 guest 中修复并复验。', '  挂载和 entrypoint 成功后仍有独立发布事务；SQLite PERSIST / synchronous=EXTRA、同步屏障、失败隔离和私有状态恢复逻辑保留。', '', '挂载内部补充诊断（单次，不当作 10 次中位数）：', '  mount-internal.json：设备可用等待 10.373 ms，ext4 2.682 ms，overlay 0.812 ms，其余目录/绑定约 1.5 ms。', '  单进程 helper 消除了多次 exec，但仍需等真实设备就绪；这解释了挂载阶段只从 41.5 降至 37.1 ms，而没有消失。', '', '验证：', '  优化前后各 fork 10 + mlink 10，全部随机标识正确且删除成功，末尾清理审计通过。', '  真实 guest：运行中的 Python 进程随父沙箱 fork，子进程 PID/nonce 与父一致；16 MiB 内存从 10 独立改成父 20 / 子 30，文件写入互不影响。', f'  采样发现父子共享 {validation["shared_sampled_pfns"]} 个非零物理页帧；KSM 状态见 manifest.json。父先销毁/子先销毁均验证存活方继续执行。', '  42 项测试通过，包括绑定提交失败、发布失败和挂载失败；未生成 memory.img，VMM/sandboxer binary 未改，继承 RAM / CoW 路径保留。', '', '准备成本：新增静态 helper 约 0.9 MiB，在 seed 建池前上传一次并验证版本；本次记录值见 mount-helper-preparation.json。', '  这是镜像无关的通用程序准备，不是提前执行本次镜像的挂载或 READY 命令；每次镜像绑定仍在计时范围内。', '', '完整证据：stages.json、baseline/、after/、*-server.log、validation.json、manifest.json、changes.patch、source/。', '  before/ 中两条连接拒绝记录发生在服务重建尚未监听时，未创建 VM，保留为就绪检查失误记录；不混入 baseline 的 10 个正式样本。', '  首次功能验证发现的 ENXIO 已修复；正式 after 组采用修复后的 helper。', '', '本轮没有改变宿主全局权限，没有停止其他人的任务，也没有调低持久化配置。', '最终代码位于 /home/huawei/src/research/sixway_startup_108/src/kuasar-fork/kuasar-io/kuasar/integrations/e2b。']
(R/'REPORT.txt').write_text('\n'.join(lines)+'\n');(R/'complete.json').write_text(json.dumps({'baseline_per_product':10,'after_per_product':10,'products':['kuasar-fork','kuasar-mlink'],'validation':True,'final_ready_pool':64},indent=2))
print(json.dumps(loads,indent=2))
