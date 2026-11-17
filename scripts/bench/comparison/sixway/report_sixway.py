from pathlib import Path
import json,statistics as st,sys,csv
r=Path(sys.argv[1]);prods=['kuasar-off','kuasar-uffd','kuasar-mlink','cube','agentenv','kuasar-fork'];names={'cube':'CubeSandbox','agentenv':'AgentENV'}
assert (r/'complete.json').exists()
rows=[json.loads(p.read_text()) for p in (r/'timing').glob('[1-5]-*.json')]
assert len(rows)==30 and all(d['success'] and not d['owned_remaining'] and all(x['success'] for x in d['pressure']) for d in rows)
lines=['# 113 机器六方沙箱测试','',f'正式结果：`{r}`。沿用 fiveway-matched-20261113_075338 的工作负载，增加 Kuasar fork；六方本轮均重新执行。运行时审计发现旧五方 mlink 实为 Python 3.12.3，因此新建同 OCI 模板修正；旧模板保留。本轮不能与旧轮数字直接混算。','',
'## 测试口径','',
'- 同一宿主机；1 vCPU、2048 MiB。Kuasar off/uffd 保持 restore prefetch=off，fork 不预先启动 Python；mlink 保持原来的 full 内存缓存策略。各产品按原五方方式创建沙箱，fork 使用预启动 seed VM。',
'- 六方使用原五方保存的同一 Python 3.12.14-slim-trixie OCI 镜像，manifest digest 为 sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79。fork 从同一归档解包，仅添加 guest agent 和运行支持文件；4406 个原镜像常规文件均逐个校验未变。各产品运行时、guest kernel 和存储实现仍各自不同。',
'- 端到端 ready：从创建请求前开始，到客户端收到 `printf READY` 为止，包含首次调用时的 SDK 导入、create 和第一次 exec；沿用原脚本每轮新客户端进程。这不是 Python print 启动耗时，也不是单独 VM 暂停耗时。',
'- 客户端沿用原脚本：mlink 使用 ttctl，其余使用 E2B SDK 2.25.1。这是各产品现有调用路径的对比，并非统一协议客户端的 VMM 微基准。',
'- 时延 5 轮，轮转产品顺序；每轮另含 8 次短 exec、CPU/IO 校验、128 MiB 内存负载，以及并发 2 的 8 个创建/计算/销毁请求。5 个 ready 样本只报告中位数、范围，不估算 P95/P99。',
'- 存储：3 轮 × 相同/不同内容 × 每组 2 沙箱，各写 32 MiB，校验摘要；内存：逐步到 50 实例，以及 50 实例各分配 20 MiB 的零值、100、随机值三种负载。',
'- 六方预检同时验证实际 Python 二进制、libpython、libc、libcrypto 的 SHA-256；对应 preflight/*.json。各产品必需的 agent、启动过程和文件系统实现仍保留各自机制。',
'- mlink 维持 64 槽位、1000 ms 补槽等待、清理并发 16。未清理全局缓存，未改变原五方性能配置。',
'- fork 的根盘只读，写入 guest RAM overlay；persistent pause/resume 不支持，标为 N/A，不能把保留 RAM 的暂停算成持久化恢复，也不能把 RAM 写入的低磁盘增量算成持久化磁盘优势；fork 的 fsync 只涉及 RAM 文件系统，不具备宿主断电后的持久化语义，IO 耗时不能作为同语义磁盘性能排名。',
'- fork 带网卡、CNI 异步执行，首次 exec 不等待 CNI；ready 不是网络就绪指标。网络和父子销毁另行验证。','',
'## 时延与吞吐','',
'| 产品 | ready 中位数 ms | 最小–最大 ms | 短 exec 中位数 ms | CPU guest ms | 32 MiB 生成/哈希/写入/fsync ms | 并发2任务/s | Python |',
'|---|---:|---:|---:|---:|---:|---:|---|']
summary={}
for p in prods:
 a=[d for d in rows if d['product']==p];assert len(a)==5
 ready=[d['ready_ms'] for d in a]
 z=dict(ready_median_ms=st.median(ready),ready_min_ms=min(ready),ready_max_ms=max(ready),short_ms=st.median(st.median(d['short_ms']) for d in a),cpu_ms=st.median(d['cpu'][1] for d in a),io_ms=st.median(d['io'][1] for d in a),throughput=st.median(d['throughput'] for d in a),platform=sorted(set(d['platform'] for d in a)))
 z['pressure_ready_median_ms']=st.median(x['ready_ms'] for d in a for x in d['pressure']);z['pressure_ready_max_ms']=max(x['ready_ms'] for d in a for x in d['pressure']);summary[p]=z
 lines.append(f"| {names.get(p,p)} | {z['ready_median_ms']:.2f} | {min(ready):.2f}–{max(ready):.2f} | {z['short_ms']:.2f} | {z['cpu_ms']:.2f} | {z['io_ms']:.2f} | {z['throughput']:.2f} | {z['platform'][0].splitlines()[-1]} |")
lines+=['', '并发压力阶段沿用已经加载的 SDK，fork 的 40 个请求 ready 中位数为 %.2f ms，最大 %.2f ms；与每轮首个请求的客户端初始化条件不同，不能直接当作相同口径的加速。' % (summary['kuasar-fork']['pressure_ready_median_ms'],summary['kuasar-fork']['pressure_ready_max_ms'])]
lines+=['','## 内存','', 'PSS 为产品服务及相关进程的合计，包含 seed/槽位/控制面。增量按各自起点扣除；共同空闲宿主内存未计入产品。50 实例为单次扩展实验。','', '| 产品 | 0 实例 PSS MiB | 50 实例 PSS MiB | 增量 MiB/实例 | 零值数组增量 MiB | 100 数组增量 MiB | 随机数组增量 MiB |','|---|---:|---:|---:|---:|---:|---:|']
for p in prods:
 d=json.loads((r/'growth'/f'{p}.json').read_text());assert d['verified']==50 and not d['owned'] and not d.get('error')
 samples=d['samples'];zero=st.median(x['pss_mib'] for x in samples[0]['resources']);last=st.median(x['pss_mib'] for x in samples[-1]['resources']);arr={}
 for m in ['default','100','random']:
  a=json.loads((r/'arrays'/f'{p}-{m}.json').read_text());assert a['success'] and not a['owned'] and not a.get('error');arr[m]=a[m]-a['python']
 summary[p]['memory']=dict(base_pss_mib=zero,pss_50_mib=last,per_instance_delta_mib=(last-zero)/50,array_delta_mib=arr)
 lines.append(f"| {names.get(p,p)} | {zero:.2f} | {last:.2f} | {(last-zero)/50:.2f} | {arr['default']:.2f} | {arr['100']:.2f} | {arr['random']:.2f} |")
lines+=['','数组增量是 50 个同时运行的 Python 进程，相对同组 Python 空运行基线的 PSS 差，不是相对空沙箱。原始时序和重叠窗口保存在 arrays/*.json。','', '## 持久化暂停与存储','', '| 产品 | 暂停中位数 ms | 恢复到 ready 中位数 ms |','|---|---:|---:|']
for p in prods:
 a=[d for d in rows if d['product']==p]
 vals=[st.median(d[k] for d in a) if all(d[k] is not None for d in a) else None for k in ['pause_ms','resume_ms']]
 lines.append('| '+names.get(p,p)+' | '+' | '.join('N/A' if v is None else f'{v:.2f}' for v in vals)+' |')
lines+=['','存储的 allocated bytes、去重后的物理 extent 并集和 PSS 均保存在 `timing/storage/storage_measurements.csv`、`storage_comparison.csv`。fork 的 live 数据在 RAM，paused2 列为 N/A。','', '## 正确性、部署与复现','',
'- 诊断轮 sixway-matched-20261117_030719（fork 镜像不一致）和 sixway-matched-20261117_032312（发现旧 mlink 的 Python 不一致）已归档并标为无效比较，不纳入本报告。',
'- 完成 30 个时延记录、36 个存储记录、24 个内存案例；240 个并发压力请求全部成功，内存案例总计创建并验证 1200 个实例。每个案例的自有实例账本均清空。',
'- 113 上的额外 fork 验证：2 GiB guest RAM，实际非零共享物理页数见验证记录；32 MiB 数据继承为 10，父/子分别写为 20/30 后互不影响；不同 IP、双向 ping、父先销毁和子先销毁都通过，未生成 memory.img。原始证明见 `validation/fork-validation.json`。',
'- fork 使用迁移的 Cloud Hypervisor 构建产物和本次为 1 vCPU 网卡队列适配重新构建的 sandboxer；在 113 上完成部署及真实 guest 验证。',
'- 源码复制至 `/home/hong/src/research/sandbox_fork` 和 `/home/hong/src/research/sandbox_bench`，保留组织目录、Git 历史和未提交修改；原机器源文件保留。省略可重建 target/node_modules/__pycache__ 和旧 AgentENV 易失运行目录，旧历史虚拟环境绝对路径不作为新部署依赖。',
'- 新部署独立位于 `/home/hong/deploy/kuasar-fork-research` 和 `/home/hong/data/kuasar-fork`；服务 `bench-kuasar-fork`，网络 namespace `bench113-fork`，端口 18884。原五方源码和结果目录保留；mlink 另建同 OCI 镜像模板，测试期间切换模板预热策略，完成后恢复旧模板策略。',
'- 新 bench 源码：`/home/hong/src/changhong94/kuasar-sandbox/scripts/bench/comparison/sixway/`；本轮冻结脚本在 `tools/`、`growth/run.py`、`arrays/run.py`，可用 `workload-hashes.json` 和迁移清单核查。',
'- 先检查其他会话没有使用这些测试服务，再以 root 执行 `python3 .../sixway/start_formal_bench.py --start`；脚本持有原 benchmark 文件锁，并检查空闲状态。',
'- seed 冷启动准备不在每次 create 内，常驻成本计入 0 实例 PSS。`validation/seed-preparation.json` 的 boot_ms 仅计 guest boot，不是镜像构建、传输、CNI 的总准备时间。','']
audit=json.loads((r/'final-audit.json').read_text());assert audit['all_six_idle'] and audit['fork_adapter_records']==0 and audit['fork_memory_img_count']==0
lines+=['最终清理审计：fork seed VMM 的 FD 数从 %d 保持为 %d；guest agent 结束时 FD 为 %d；仅保留 seed VM 及其一个 IPAM 租约，派生实例全部销毁。详见 final-audit.json。' % (audit['fork_seed_vm_fds_initial'][0],audit['fork_seed_vm_fds'],audit['fork_guest_agent_fds_at_end']), '']
(r/'REPORT.txt').write_text('\n'.join(lines));(r/'summary.json').write_text(json.dumps(summary,indent=2));print(r/'REPORT.txt')
