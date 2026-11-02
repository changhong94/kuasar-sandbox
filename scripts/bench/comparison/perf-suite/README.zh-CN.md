# 三方性能专项（功能试跑版）

对象为 Kuasar（关闭内存预取）、CubeSandbox、AgentENV。使用已部署的证书任务模板，不调用模型、不修改 TB2 原始评分、不修改运行服务。所有输出目录必须是新目录；中断后先检查实例账本，不能直接重复启动。

## 运行

使用现有 skyrl-rollout Python 环境（含 Harbor、E2B）；需 root 读取宿主机进程统计、管理本轮 hosts 条目。凭据从原有受保护配置读取，不复制到结果。

```bash
sudo /home/hong/src/.deployment/terminal-bench-pilot/verifier-tools/uv run --isolated --no-project -- \
  /home/hong/src/.deployment/skyrl-rollout/venv/bin/python \
  scripts/bench/comparison/perf-suite/run_suite.py \
  --output /home/hong/src/.deployment/perf-threeway-$(date +%Y%m%d_%H%M%S)
```

可通过 `--cases runtime memory` 或 `--products kuasar` 缩小修复验证范围。每个 worker 只管理自己创建的实例；持有既有三方 benchmark 锁。异步开放请求超过客户端在途上限时明确记作客户端拒绝，不算服务端拒绝。失败保留，不能从分母排除。

`--profile extended --isolated-host-confirmed` 执行三轮、实例数 1/4/8、持续 60 秒的多档到达速率。这个参数是操作者对独占窗口的确认，不是自动证明机器独占。正式测试需要更多独立样本再报告尾分位数；smoke 不输出性能排名。

## 已实现的测试入口

| case | 测量和验证 |
|---|---|
| certificate | 固定 14 条命令分别调用 / 单次批处理；原始评分；批处理包含 Python 调度和 bash 子进程，差值不是纯虚拟化开销 |
| runtime | 创建到探测成功；12 次空命令；256 MiB SHA256 计算（客户耗时、客体耗时、CPU 时间）；32 MiB fsync 写入和冷读建议/暖读；1 KiB/1 MiB 上传、下载及字节校验 |
| memory | 128 MiB mmap 分配、全部写入、校验、munmap；释放后 5/15 秒观察；宿主机每秒采样 |
| resume | 暂停与恢复；原实例文件标记正确性验证；不是全新模板冷启动 |
| density | 多实例驻留；逐实例增加及删除后的进程 PSS、cgroup、宿主机视图 |
| storage | 低熵/高熵，独立实例相同/不同内容；文件和平台空间；暂停保存后恢复文件 SHA256 验证 |
| pressure | 固定并发与固定到达速率；创建+相同哈希工作+清理；成功、失败、客户端拒绝都保存 |
| recovery | 突发请求后再探测 1/5/15 秒；实际时间戳保留，探测自身也会改变系统状态 |

宿主机采集覆盖产品选定进程（包含共享服务和已存在实例）、PSS/匿名/文件/共享页、CPU 时间、线程、文件描述符、上下文切换、进程 I/O、cgroup memory/cpu/io、宿主机内存/压力/磁盘计数。PSS、cgroup 与宿主机占用不可相加。进程计数差可能遗漏已退出进程，需结合 cgroup 累计计数；重启/计数器复位不可当成负消耗。

文件逻辑大小和分配大小分别输出。共享/reflink 数据块可能重复计入分配大小；worker 的 `--extents` 使用相同文件系统内的 FIEMAP 区间并集，不能跨文件系统直接合并。全局目录的变化在共享机器上不是本轮专属成本。AgentENV 与另两者的底层存储布局不同，正式 I/O 对比前必须对齐或单列差异。

## 已登记、不能冒充已验证的项目

1. 真正冷启动、文件缓存/应用缓存分层对照：需独占环境、核实控制点；不做全机 drop_caches。
2. 服务启动与预热资源池成本、池大小消融：需版本匹配源码及隔离测试部署，不能重启现有共享服务。
3. 模板首次导入耗时及存储成本：重新导入独立命名模板才能测，不能由现有模板倒推。
4. 原生 CPU/I/O 对照：先统一 Python、OpenSSL、依赖和 CPU 绑定；未匹配时不计算额外开销百分比。
5. 独立导出的保留快照：本套新入口测 API 暂停产物，已有 Kuasar/Cube 发布快照 extent 专项另行保留；不能把两种语义混合。
6. 深度采样（page fault、块 I/O、调度、io_uring 等）：异常诊断轮次使用，不与轻量计时轮次混合。

这些项目也记录在每次输出的 plan.json 中，避免遗漏。未支持/未执行不是 0。

## 数据

`plan.json`、`sources/`、`source-hashes.json` 固定方案和实现；`progress.json` 记录进度；每轮 `result.json`、`telemetry.jsonl` 为原始数据；证书轮保留原始 Harbor 评分和命令哈希；`summary.json/csv` 机械汇总。`blocked.json` 表示停止等待修复，`complete.json` 只表示本轮计划跑完，不表示正式性能结论成立。

`paired.csv` 给出相同条件下相对 CubeSandbox 的百分比，但 smoke 数据明确标记不用于排名。`validate.py OUTPUT` 生成独立 `validation.json`，核对原始评分、固定命令数量、数据内容是否满足相同/不同设定、资源采样是否报错和实例清理。校验不会覆盖原始记录。

源码版本和独立修改分支见 `source-checkouts.json`，冷启动/预热/恢复相关入口见 `source-map.json`。产品源码当前未打性能补丁，运行服务未因本套脚本重构建或重启。

正式报告以后统一重生成，此次不覆盖先前待审阅的 PDF。
