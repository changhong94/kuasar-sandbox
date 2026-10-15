# Alice 上的源码构建与 bench

源码：`/home/hong/src/kuasar-sandbox/`，包含六个官方仓库。
脚本：当前 fork 的 `scripts/bench/`；原始 bench 与准备、构建、部署脚本统一放在这里。
私有状态和测试结果：`/home/hong/src/.deployment/`，不提交到 Git。


## 一键准备与清理

```bash
python3 ~/src/changhong94/kuasar-sandbox/scripts/bench/prepare-bench.py --check
python3 ~/src/changhong94/kuasar-sandbox/scripts/bench/prepare-bench.py
```

`--check` 只读检查，依赖缺失返回 1。普通模式仅安装缺失的 apt 包及锁定版本的
Python 包；依赖齐全时不运行 apt update/install 或 pip install。
默认虚拟环境为实际调用用户的 `~/src/.deployment/bench-venv`，sudo 调用也不会改成 `/root`。
支持 `--venv /绝对路径` 指定新虚拟环境。Python 包不安装到系统 Python。
已有 Python 版本与锁定版本不符时停止，可另建虚拟环境；apt 预演若需要升级或删除已有包也停止。
依赖安装阶段不执行 apt upgrade、自动修复 dpkg 或改变已有工具链。
默认随后编译官方源码、部署独立节点并等待健康检查通过；已存在且健康时复用部署，不重启。
已有异常或不完整部署时停止，保留诊断信息。部署会创建本环境的网络、证书和服务。
系统首次安装依赖本身仍会写文件并执行发行版的包安装钩子，建议避免同时运行其它包管理操作。

依赖范围是 Ubuntu 上源码构建所需的编译库、命令行工具以及 bench SDK。
Go、Rust、Docker 和 KVM 仅检查，不自动安装或配置：本机已有 `.tools` 工具链与 Docker。
新的空白机器仍需先准备这些前置条件；当前部署脚本仍包含 hong 的机器配置，
目录改名不代表部署脚本已经支持任意机器。
机器特例的 `/lib32` 修复和系统包修复不属于本脚本。

## 构建

```bash
bash /home/hong/src/changhong94/kuasar-sandbox/scripts/bench/build-official.sh
```

使用 `/home/hong/src/.tools` 中的 Go/Rust 和独立依赖缓存。
实际源码提交及工具链版本记录在 `.deployment/build-versions.txt`。
编译并发默认 4。直接调用 build-official.sh 不更新源码或管理补丁；完整 prepare-bench.py 入口在构建前自动管理计时补丁。

## 部署

```bash
bash /home/hong/src/changhong94/kuasar-sandbox/scripts/bench/deploy-source.sh
sudo journalctl -u kuasar-hong-node -f
```

启动前拒绝覆盖已有同名服务。部署基于当前官方 Demo 的配置与资源所有权检查，
生成独立 Store/Cache/Registry、交换机、Conductor/Proxy 和 Python 快照模板。
准备完成的标志为 `KUASAR_HONG_NODE_READY`。
当前配置使用本机 HTTPS 127.0.0.1:443（控制）和 127.0.0.2:443（数据）。
访问配置保存在 `.deployment/access.json`，权限 0600，由 root 读取。
服务重启会重新生成节点运行目录和测试模板。

## 小规模 bench

```bash
sudo /home/hong/src/.deployment/bench-venv/bin/python \
  /home/hong/src/changhong94/kuasar-sandbox/scripts/bench/run-bench.py \
  --prefetch memory --warmup 1 --samples 3
```

包装脚本调用 `scripts/bench/bench.py` 的 `run_round`，探针为
`echo BENCH_OK; python3 --version`。每轮创建一个沙箱、执行首次与第二次命令，
再删除并验证 API 返回 404。不会执行原脚本的直接目录删除。
运行结果写入 `.deployment/bench-smoke-YYYYMMDD_HHMMSS/`。
正式测量前应另行控制缓存状态和共享主机负载；三次试跑不作为性能基准。
官方源码若不提供 launchTiming/launchMs，则只记录可观测的客户端指标。

两个历史 patch 保留作为兼容候选；优先使用 patches/ 下适配当前版本的计时补丁。
`e2b-env.sh` 中的旧 API Key/Access Token 已清空；实际配置通过私有环境文件加载。
不要将 access.json、local.env、TLS 私钥或运行目录提交到仓库。

## 本次试跑记录

2026-10-15：memory，串行，预热 1 次、正式 3 次，全部成功。
E2E：359.54 / 515.71 / 705.20 ms，中位数 515.71 ms。
结果目录：`/home/hong/src/.deployment/bench-smoke-20261015_103700/`。
依赖版本见 `requirements.lock.txt`。本次没有应用旧计时补丁。

部署生成脚本修正了 Docker containerd 镜像 ID 与配置摘要不同的兼容问题，
通过导出镜像并计算配置摘要进行校验；官方仓库源码保持不变。
可选 S3 测试工具 VersityGW 的构建已停止，本次文件后端部署无需该工具。

## 准备入口的范围

```bash
# 默认：依赖 -> 计时补丁 -> 编译 -> 部署 -> 等待就绪；不自动跑 bench
python3 prepare-bench.py
# 仅依赖
python3 prepare-bench.py --deps-only
# 依赖及编译（已有部署时拒绝覆盖运行中的二进制）
python3 prepare-bench.py --build-only
```

`--check` 仍只检查依赖，不编译或部署。完整部署当前针对 hong@alice，
使用已有 Go/Rust、Docker 与基础镜像，详见 deploy-source.sh。
依赖安装与完整部署可使用普通用户调用，必要步骤自动 sudo。

## 清理入口

```bash
python3 clear-bench.py --dry-run
python3 clear-bench.py                   # 部署 + 编译
python3 clear-bench.py --deployment-only # 只清理部署
python3 clear-bench.py --build-only      # 只清理编译；必须先停止/清理部署
```

部署清理会删除本环境的沙箱、快照、Store/Cache/Registry 数据，以及两个
kuasar-hong 服务和生成的访问配置。先调用现有部署的退出清理逻辑，回收它拥有的
网络与动态服务；归属不匹配或退出清理不完整时停止，不强制删除遗留状态。
不删除其他用户的 Kuasar、不卸载系统依赖、不清理 Docker 共享镜像。

编译清理调用五个组件各自的 `make clean`，并移除官方聚合仓库的 bin 和 build 下的构建产物，但保留 `build/tarball/`。
保留源码与 Git 修改、native-deps 下载/源码目录、聚合仓库 `build/tarball/` 下载文件及校验文件、.tools、Python venv 和历史 bench 结果。
清理后再运行 `prepare-bench.py` 可重新构建与部署。
本次只运行清理预演和隔离逻辑测试，没有实际删除正在运行的环境。

## 计时补丁

prepare-bench.py（默认及 --build-only）在编译前检查 orchestrator/sandboxer 两个补丁。
先对两个仓库全部预检，已应用（反向检查通过）则跳过；未应用且正向检查通过则应用。
部分应用、上下文冲突或修改重叠时停止，不执行 git reset/checkout 覆盖源码。
适配补丁位于 patches/，保留原有 AssignWithFence 逻辑，并适配新的 RuntimeSpec 计时传递。
构建及 verify-prebuilt 成功后保存 .deployment/timing-build.json；现有无补丁部署不自动复用，
会提示先 clear-bench.py 再 prepare-bench.py。SDK 依赖阶段单独 --deps-only 不修改补丁。

clear-bench.py 默认及 --build-only 在清理构建后反向撤销计时补丁，已撤销则跳过。
--deployment-only 保留源码补丁。清理开始前预检撤销是否安全；冲突时先停止，保留用户修改。
撤销只涉及补丁的差异，不恢复整个文件；其他不冲突的修改保留。
操作补丁不会修改 Git HEAD 或创建提交。
