# Kuasar 基准测试环境

[English](README.md)

本目录包含 bench、依赖准备、源码编译、部署、清理和内部阶段计时补丁。

## 适用范围与工作目录

从本仓库根目录执行下面的命令。后续命令均假定当前目录为 `scripts/bench`：

```bash
cd scripts/bench
```

当前生命周期脚本面向已有的 Alice 部署，部分脚本仍包含机器特定的路径、服务名、
网络配置和基础镜像 ID。用于其他机器前，请检查 `bench_lifecycle.py`、
`deploy-source.sh`、`prepare-node.py`、`prepare-storage.py` 和 `run-bench.py`。
本文使用相对命令不代表这些脚本已经支持任意机器。

源码按组织隔离，六个官方仓库与本 fork 分开存放：

```text
<源码目录>/
  kuasar-sandbox/
    kuasar-sandbox/
    accelerator/
    connector/
    guest-runtime/
    orchestrator/
    sandboxer/
  <fork-owner>/kuasar-sandbox/scripts/bench/
  .tools/
  .deployment/
```

下文中的 `.deployment` 和 `.tools` 均位于源码目录下，而非本仓库内。
私有部署状态和测试结果保存在 Git 仓库之外。

## 准备依赖、编译与部署

```bash
python3 prepare-bench.py --check       # 仅检查依赖
python3 prepare-bench.py               # 依赖 -> 补丁 -> 编译 -> 部署
python3 prepare-bench.py --deps-only    # 仅安装依赖
python3 prepare-bench.py --build-only   # 依赖、补丁和编译
```

默认命令会等待部署就绪，但不会自动跑 bench。只有健康且计时补丁构建记录匹配的
已有部署才会被复用。未打补丁、不完整或异常的部署不会被覆盖：先检查问题，
或执行 `clear-bench.py` 后重新准备。

依赖准备只安装缺失的 apt 包及 `requirements.lock.txt` 中固定版本的 Python 包，
不升级已有包。Python 版本冲突，或 apt 安装计划需要升级、删除已有包时会停止。
依赖齐全时跳过 apt update/install 和 pip install。首次安装系统包仍会执行发行版的安装钩子。

Python 包安装在独立的 `.deployment/bench-venv` 中。依赖安装器在 sudo 下仍使用
实际调用用户的主目录。`--venv` 可配合 `--deps-only` 或 `--check` 指定其他环境；
完整部署使用其配置的虚拟环境。Go、Rust、Docker 和 KVM 仅检查，不自动安装配置。
系统包修复及机器特定的文件系统修复不在此脚本范围内。

## 编译与部署辅助脚本

```bash
bash build-official.sh
bash deploy-source.sh
sudo journalctl -u kuasar-hong-node -f
```

这些是底层辅助入口；完整流程优先使用 `prepare-bench.py`。
编译入口使用本地 `.tools` 工具链和依赖缓存，默认并发 4，源码提交及工具链版本
记录在 `.deployment/build-versions.txt`。它本身不更新源码，也不管理计时补丁。

部署创建独立的 Store、Cache、Registry、交换机、Conductor/Proxy 和 Python 快照模板，
拒绝覆盖已有服务定义。就绪标志为 `KUASAR_HONG_NODE_READY`。
当前 HTTPS 控制入口是 `127.0.0.1:443`，数据入口是 `127.0.0.2:443`。

访问配置保存在 `.deployment/access.json`，权限为 root 专用的 0600。
重启节点服务会重新生成运行目录和测试模板。

## 运行 bench

使用独立虚拟环境中的 Python，不使用系统 Python。针对当前源码布局，先设置解释器：

```bash
BENCH_PYTHON="$HOME/src/.deployment/bench-venv/bin/python"
sudo "$BENCH_PYTHON" run-bench.py --prefetch memory --warmup 2 --samples 10
```

将 `memory` 改成 `off` 可关闭内存预取。测试串行运行，每轮创建沙箱，两次执行
`echo BENCH_OK; python3 --version`，再删除沙箱并确认其 API 返回 404。
包装脚本调用 `bench.py` 的 `run_round`，将原来的直接目录清理替换为 API 检查。

结果保存在 `.deployment/bench-smoke-YYYYMMDD_HHMMSS/`：

- `samples_*.jsonl`：每轮详细记录，包含预热及可用的阶段计时数据。
- `samples_*.csv`：选定的逐轮指标。
- `summary_*.json`：正式样本数量及 E2E 最小值、中位数、最大值。

内部阶段计时需要带补丁的构建。接口没有 `launchTiming`/`launchMs` 时，仅记录
可观测的客户端指标。此包装脚本不执行原来的 OpenClaw 业务，也不生成完整的逐阶段 P95 报告。
比较性能前，需要统一业务探针、样本量、缓存状态和主机负载。

部署用户可浏览结果；包含凭据的 `local.env` 仍仅 root 可读。
不要提交访问配置、环境凭据、TLS 私钥或运行目录。`e2b-env.sh` 是凭据已清空的历史示例，
包装脚本实际使用生成的私有环境文件。

## 清理环境

```bash
python3 clear-bench.py --dry-run
python3 clear-bench.py                    # 部署、编译及计时补丁
python3 clear-bench.py --deployment-only  # 保留构建产物和源码补丁
python3 clear-bench.py --build-only       # 部署仍在运行时拒绝执行
```

部署清理会删除本环境的沙箱、快照、Store/Cache/Registry 数据、两个 `kuasar-hong` 服务
及生成的访问配置。首先调用本部署的退出清理逻辑，回收其拥有的网络和动态服务。
资源归属不匹配或退出清理未完成时停止，保留诊断状态。
其他用户的 Kuasar、系统依赖及 Docker 共享镜像会保留。

编译清理调用五个组件的 `make clean`，删除聚合仓库的构建产物，但保留
`build/tarball/` 下载文件及校验文件。native 依赖的源码与下载缓存、`.tools`、Python
虚拟环境、历史 bench 结果及不相关的源码修改也会保留。之后可用 `prepare-bench.py` 重新构建。

## 计时补丁

准备流程先预检 orchestrator 和 sandboxer 两个补丁，再进行修改。
反向检查通过表示已应用，直接跳过；正向检查通过则可以应用。
部分应用或源码冲突时停止，不重置源码文件。

适配补丁位于 `patches/`，旧版作为兼容候选保留。
标有 `Timing patch adaptation:` 的注释说明了针对当前 `AssignWithFence` 和
`RuntimeSpec` 流程的适配。构建验证成功后写入 `.deployment/timing-build.json`，
供后续部署复用检查使用。

默认清理和 `--build-only` 在清理构建产物后反向撤销补丁；已撤销则跳过。
`--deployment-only` 保留补丁。停止部署前会检查能否安全撤销，并保留不相关的源码修改。
补丁管理不改变 Git HEAD，也不创建提交。
