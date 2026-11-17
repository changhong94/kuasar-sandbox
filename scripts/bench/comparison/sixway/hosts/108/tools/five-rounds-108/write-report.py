from pathlib import Path
import json,statistics
R=Path('/opt/bench108/results/five-rounds-108')
load=lambda p:json.loads(p.read_text())
final=load(R/'round5/stages.json');prep=load(R/'round5/preparation.json');refill=load(R/'round5/refill-events.json')
lines=['108: 五轮优化与真实解释器启动对比（2026-11-17）','',
'结论：最终部署保留第1、2、5轮；第3、4轮已回退。Node.js、Ruby在最终同轮10次测试中，中位数和最大值均低于mlink。仅代表本机、本次镜像/负载和样本，不保证所有镜像或尾延迟SLA。',
'计时：客户端创建请求开始，到收到新启动解释器打印的随机标识；包含解释器启动。每产品/语言10次，两并发、交错测试，未重试/丢弃样本。准备/补槽/销毁不在创建到print计时内，单独列出。',
'使用隔离mlink实例，原bench108-mlink服务未重启；未终止其他用户进程。共享机器负载未受控，差异不能全部归因于代码。',
'同一固定amd64 digest、同一root.ext4内容、同一命令/环境/计时点；脚本hash与language-matched-108/bench.py一致。Node: node:22-bookworm-slim@sha256:47725aca53d3295ec2d3be8f62726599b3033cc262edc2c7e429909b3ac599fc；Ruby: ruby:3.3-slim-bookworm@sha256:51d211cdbd0b226c7bbae9a377ed5731eaf2acb728000096061c01d360ed213d。',
'注意：没有语言专用路径、专用VM池或提前运行解释器。新增统一regular-file缓存会使应用二进制/库进入guest页缓存，属于通用预热，不能称为冷缓存启动。每镜像仍需独立不可变文件模板，共享64个通用VM槽。',
'', '最终结果，ms：语言 | fork中位数 | fork最大 | mlink中位数 | mlink最大']
for l,a in final.items():
 f=a['kuasar-fork'];m=a['kuasar-mlink'];lines.append(f"{l} | {f['ready_ms']:.3f} | {f['max_ms']:.3f} | {m['ready_ms']:.3f} | {m['max_ms']:.3f}")
lines+=['','任务开始前历史基线（非同时采样）：Node fork 173.463/255.944 ms，Ruby fork 162.976/173.887 ms。','', '额外五轮：每项数值均为该轮10次中位数/最大值，ms。']
names={1:'统一有界镜像文件缓存；保留',2:'Netlink取代tc子进程解除网络屏障，等待kernel ACK；保留',3:'在RPC任务内同步执行熵/冻结检查，减少worker排队；中位数/身份RPC无改善，回退',4:'snapshot VM halt-poll由200us增至1ms；中位数无改善、CPU增加，回退至200us，未改宿主全局值',5:'冻结证明持有freezer.state FD，按偏移读写并检查冻结状态，成功解冻后关闭；保留'}
for i in range(1,6):
 d=load(R/f'round{i}/stages.json');lines.append(f'第{i}轮：{names[i]}')
 for l,a in d.items():lines.append(f"  {l}: "+'; '.join(f"{p} {v['ready_ms']:.3f}/{v['max_ms']:.3f}"for p,v in a.items()))
lines+=['', '此前另做的metadata-only、同步raw后端实验保存在restore-exec-opt-108及restore-exec-sync-108；后者没有稳定收益，已回退，不计入额外五轮。',
'', '阶段解释：历史KVM恢复增加约4ms的精确原因无法从旧日志证明。新增CH_RESTORE_TIMING按设备、CPU状态、线程启动和调度分段，KVM对象复用和RAM注册路径未重复构建整份RAM。相同代码在不同轮有明显调度/同步波动。',
'最终阶段中位数（各阶段中位数不可相加当成总中位数）：']
for l,a in final.items():
 f=a['kuasar-fork'];lines.append(f"{l}: 创建API={f['api_ms']:.3f}ms, exec到print={f['exec_to_print_ms']:.3f}ms; bind={f['bind_ms']:.3f}ms; "+json.dumps(f['bind_phases_ms']))
lines+=['Netlink的目标阶段第1->2轮：Node1.976->0.465ms，Ruby1.848->0.274ms。',
'FD复用第2->5轮冻结检查work：Node0.2805->0.1675ms、Ruby0.429->0.142ms；整体身份RPC不是两语言均改善。最终端到端的大幅改善还包含KVM/调度差异，不能全归给0.1~0.3ms的小改动。',
'首次解释器回退的诊断：Node/Ruby重复执行明显快于首次；Ruby大量open/stat/readlink以及库读取，Node二进制首次页加载，统一metadata-only不足。主收益来自统一有界regular-file缓存，准备成本明确移到了模板生成，解释器执行本身仍在计时内。',
'', '准备成本（只生成文件模板，不按语言另建VM池）：']
for l,p in prep.items():
 c=p['metadata_cache'];lines.append(f"{l}: 模板准备{p['preparation_ms']:.3f}ms（包含统一缓存RPC {c['rpc_elapsed_ms']:.3f}ms，读取{c['regular_file_bytes_read']}bytes）；宿主RAM文件预热{p['warmup_ms']:.3f}ms；64槽metadata staging {p['metadata_stage_ms']:.3f}ms。startup_read_files为空，application_executed=false。")
dep=load(R/'round5/deploy.json');lines.append(f"64槽准备{dep['ready']['preparation_ms']:.3f}ms；service启动到三模板/全池可用{dep['service_start_to_ready_ms']:.3f}ms。首次重建因测试盘满失败，清理15个本试验停用且未映射的RAM文件后重建成功；该失败发生在正式测试前，日志保留。")
for l in ['node','ruby']:
 d=load(R/f'round5/mlink-preparation-{l}.json');lines.append(f"mlink {l}: 本轮已有模板的prewarm启用等待{d[l]['elapsed_ms']:.3f}ms，不是从零导入成本；原import记录另见mlink-import.json。")
for k in ['elapsed_ms','replacement_ms']:lines.append(f"补槽20次 {k}: 中位数{statistics.median(x[k] for x in refill):.3f}ms，最大{max(x[k] for x in refill):.3f}ms。replacement包含1000ms补槽延迟及排队。")
res=load(R/'round5/final-resources.json');lines+=['',f"资源：64槽、0 assigned；服务cgroup {res['processes']}进程，PSS={res['totals']['Pss']}KiB，RSS求和={res['totals']['Rss']}KiB，FD前后均2239。PSS不含未映射的模板文件页缓存，不能当作全部成本：三份2GiB模板RAM文件总计6GiB，实际驻留/分配见final-audit.json。CoW页及通用缓存也有内存成本。",'',
'验证：40个正式请求均首试成功、随机标识匹配、已销毁。父/子同PID与nonce继续运行，16MiB状态分别改20/30互不影响，采样324个共享PFN；父先销毁、子先销毁、父销毁后孙代均通过。Node/Ruby分别执行、销毁后存活者执行通过。',
'独立MAC/IP/CID、互通HTTP、private(rw-p)RAM映射通过。运行中fork保留父TCP，子继承连接reset后可新建；模板TCP监听者回退完整清理，伪造skip无效。冻结期间exec关闭、错误owner/错误网络不释放gate、staging身份不匹配拒绝且回收、证书FD释放通过。',
'保留同步/持久化屏障、sqlite持久化配置、网络隔离和CoW；模板可以生成memory-ranges文件，不做每请求全量RAM复制。没有删除fsync或缩短安全等待以换性能。',
'', '部署与复现：源码仍在原sandbox_fork工作树（包含原有未提交研究修改，不整体提交）。final-source/保存本次相关源码及相对备份patch；final-source-manifest.json和final-audit.json记录身份。',
'最终运行：/opt/bench108/deploy/fork/bin/sandboxer、/opt/bench108/deploy/fork/bin/cloud-hypervisor；runtime=/opt/bench108/assets/fork-runtime-five-round5.ext4。',
'注意build/snapshot-ch/release/cloud-hypervisor是已拒绝第4轮的1ms实验产物，不是最终部署二进制；最终CH使用round4/before/cloud-hypervisor（200us）。后续构建请用当前已回退源码，勿盲目安装旧build产物。',
'脚本：tools/five-rounds-108/round5/bench.py、run-bench.py、analyze.py及七个validate脚本；配置和原始40样本均在round5/。完整5轮均保留，未按结果删除慢样本。',
'性能指标仅是本次10样本的中位数/最大值，不外推P99或所有新镜像；超过512MiB预算的镜像不保证全文件预热。']
(R/'REPORT.txt').write_text('\n'.join(lines)+'\n')
print('report written')
