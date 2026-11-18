from pathlib import Path
import json,sys
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.graphics import renderSVG
from plot_helpers import chart
B=Path(sys.argv[1]);O=B/'report';O.mkdir(exist_ok=True)
x=json.loads((B/'summary.json').read_text());old=json.loads((B/'before/summary.json').read_text());mid=json.loads((B/'round1/summary.json').read_text())
r=json.loads((B/'results/burst256/kuasar-fork/result.json').read_text());baseline=json.loads((B/'before/result.json').read_text())
proof=json.loads((B/'disk-backing-verification.json').read_text());assert all(z['success'] for z in proof['rows']) and not proof['owned']
for name in ('warmup','01'):
 z=json.loads((B/f'live-fork-validation/python/{name}/result.json').read_text());assert z['success'] and not z['owned_remaining']
assert r['batch_valid'] and r['all_private_files_verified'] and r['survivors_verified_after_half_destroyed'] and not r['public_remaining']
p=[json.loads(l) for l in (B/'results/burst256/kuasar-fork/pool-events.jsonl').read_text().splitlines()];p=sorted([z for z in p if z['event']=='prepared' and z['reason']=='refill'],key=lambda z:z['monotonic_ns'])
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
styles={k:ParagraphStyle(k,fontName='STSong-Light',fontSize=n,leading=n*1.45,spaceAfter=8,wordWrap='CJK') for k,n in [('title',18),('body',10),('small',8)]};story=[]
def txt(t,style='body'):story.append(Paragraph(t,styles[style]))
def table(rows,widths):
 t=Table([[Paragraph(str(c),styles['small']) for c in row] for row in rows],colWidths=widths);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4edf4')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t)
def f(v):return f'{v:,.2f}'
for en in (False,True):
 def tr(c,e):return e if en else c
 if story:story.append(PageBreak())
 txt(tr('fork 并行补槽：256 并发创建','fork parallel refill: 256 concurrent creates'),'title')
 txt(tr('113 / sandbox_fork_staging / 64 个预备槽。每版一次 256 请求突发测试，另有一次排除的 warmup；成功实例全部保留到本轮结束后统一销毁。','Host 113 / sandbox_fork_staging / 64 reserves. One 256-request burst per version plus one excluded warmup. All successful instances retained until the batch finishes.'))
 table([[tr('版本','Version'),tr('全部 print / 秒','All print / s'),tr('相对原版','Vs baseline')],[tr('原串行补槽','Serial baseline'),f(old['all_print_ms']/1000),'—'],[tr('第一轮：8 线程、按记录提交','Round 1: 8 workers, per-record commits'),f(mid['all_print_ms']/1000),f((1-mid['all_print_ms']/old['all_print_ms'])*100)+'%'],[tr('本轮：加原生锁拆分与定向唤醒','Final: native lock handoff + targeted wakeup'),f(x['all_print_ms']/1000),f((1-x['all_print_ms']/old['all_print_ms'])*100)+'%'],['AgentENV '+tr('此前同口径批次，仅作参考','previous comparable batch; reference only'),'7.69','—']],[300,100,100])
 txt(tr('时间起点为统一释放 256 个客户端线程；Ready 为客户端收到 shell 随机标识，print 为收到新启动 Python 输出的随机标识及换行，包含解释器启动。两者不等于 HTTP 创建响应。','Time zero is release of all 256 client workers. Ready means receipt of a random shell marker; print means receipt of a random marker/newline from a newly started Python interpreter, including startup. Neither means only the HTTP create response.'))
 txt('python:3.12-slim — '+x['image_digest'],'small')
 txt(tr('2 vCPU / 2 GiB；同一镜像、命令与计时起止点；无语言专用预热。实际客户端分发跨度 '+f(x['client_dispatch_spread_ms'])+' ms。','2 vCPU / 2 GiB; same image, command and timing boundaries; no language-specific prewarming. Actual client dispatch spread: '+f(x['client_dispatch_spread_ms'])+' ms.'))
 txt(tr('256/256 创建、Ready 和 print 成功。全部 Ready：'+f(x['all_ready_ms']/1000)+' 秒；全部运行且 64 槽补满：'+f(x['full_reserve_after_request_release_ms']/1000)+' 秒。','256/256 create, Ready and print succeed. All Ready: '+f(x['all_ready_ms']/1000)+' s; all running plus 64 reserves restored: '+f(x['full_reserve_after_request_release_ms']/1000)+' s.'))
 txt(tr('每个版本只测一次突发，总完成时间不是多轮中位数。后页的分位数对应该批次内的相邻完成间隔或单个补槽。','One burst per version: total completion time is not a median across batches. Subsequent quantiles describe within-batch completion gaps or individual refills.'))
 story.append(PageBreak());txt(tr('准备与领取路径瓶颈','Preparation and claim-path bottlenecks'),'title')
 txt(tr('改动：8 个有上限的补槽线程；原子预留容量；单记录持久化提交；新槽以自身生命周期锁保护网络/KVM 准备；一个 Ready 槽只唤醒一个领取者。运行中父沙箱 fork 仍使用原安全屏障。','Changes: 8 bounded workers; atomic reserve accounting; per-record durable commits; per-sandbox lifecycle locking during network/KVM preparation; one Ready slot wakes one claimant. Live-parent fork keeps its original safety gate.'))
 rows=[[tr('阶段（独立计时，勿直接相加）','Stage (separate timers; do not sum)'),tr('样本数','Samples'),tr('中位 ms','Median ms'),tr('最大 ms','Max ms')]]
 labels=[('prepare/create_record','创建记录与锁等待','Create record / lock'),('prepare/namespace','网络命名空间准备','Namespace preparation'),('prepare/admin:sandbox-pool-prepare','原生网络/KVM 准备 RPC','Native network/KVM RPC'),('prepare/admin:sandbox-snapshot-stage','快照元数据暂存 RPC','Snapshot metadata stage RPC'),('claim/pool_assignment_save','领取持久化提交','Durable claim'),('claim/pool_lease','领取（含缺槽等待）','Claim incl. reserve wait'),('claim/snapshot_bind','子 VM 快照绑定恢复','Child snapshot bind/restore'),('claim/oci_entrypoint_start','OCI 入口进程启动','OCI entrypoint launch')]
 for k,c,e in labels:
  v=x['host_phases'].get(k)
  if v:rows.append([tr(c,e),v['n'],f(v['median']),f(v['max'])])
 table(rows,[290,60,75,75])
 rows=[[tr('原生准备子阶段','Native preparation phase'),tr('样本数','Samples'),tr('中位 ms','Median ms'),tr('最大 ms','Max ms')]]
 for k in ('transaction_lock','profile_read','create_slot','network_identity','network_prepare','network_gate','kvm_prepare','identity_dump'):
  v=x['native_phases'].get(k)
  if v:rows.append([k,v['n'],f(v['median']),f(v['max'])])
 table(rows,[290,60,75,75])
 txt(tr('journald 限流丢弃了部分原生/RPC 日志，表中明确列出实际样本数，不视为全批次分布。独立补槽事件文件完整记录了 256 个任务。原生子阶段包含在准备 RPC 内。Ready 发布仍等待网络和设备成功及持久化提交；没有删除同步屏障。','Journald rate-limited some native/RPC logs; their sample counts are explicit and are not full-batch distributions. The separate refill event file contains all 256 jobs. Native subphases are included in the preparation RPC. Ready publication still waits for successful network/device work and a durable commit; no sync barrier was removed.'),'small')
 story.append(PageBreak());txt(tr('完成时间与相邻完成间隔','Completion timeline and adjacent intervals'),'title')
 for name,title,key,scale,ylabel in [('completion-timeline',tr('Python print 完成时间','Python print completion'),'completion_ms',1000,tr('实际耗时 / 秒','Elapsed / seconds')),('completion-intervals',tr('相邻两次完成的间隔','Adjacent completion intervals'),'adjacent_completion_gap_ms',1,tr('间隔 / ms','Gap / ms'))]:
  series=[(label,[(i,t/scale) for i,t in enumerate(data['print'][key],1 if key=='completion_ms' else 2)],color) for label,data,color in [('Serial baseline',baseline,'#a7afb6'),('Parallel final',r,'#236aa0')]]
  d=chart(series,title,ylabel,en,height=270);story.append(d)
  if not en:renderSVG.drawToFile(d,str(O/(name+'.svg')))
 v=x['completion_gap_ms'];txt(tr('255 个相邻完成间隔：中位 '+f(v['median'])+' ms；P95 '+f(v['p95'])+' ms；P99 '+f(v['p99'])+' ms；最大 '+f(v['max'])+' ms。','255 adjacent completion gaps: median '+f(v['median'])+' ms; P95 '+f(v['p95'])+' ms; P99 '+f(v['p99'])+' ms; max '+f(v['max'])+' ms.'))
 story.append(PageBreak());txt(tr('补槽、准备成本与独立性验证','Refill, preparation cost and isolation validation'),'title')
 d=chart([('Parallel final',[(i,z['elapsed_ms']) for i,z in enumerate(p,1)],'#236aa0')],tr('每次补槽的实际准备耗时','Actual preparation work per refill'),tr('实际耗时 / ms','Elapsed / ms'),en,height=250,x_label=tr('完成的第几个补槽','Refill completion rank'));story.append(d)
 if not en:renderSVG.drawToFile(d,str(O/'refill-times.svg'))
 rows=[[tr('指标','Metric'),tr('中位 ms','Median ms'),'P95 ms','P99 ms',tr('最大 ms','Max ms')]]
 for k,c,e in [('refill_work_ms','补槽实际准备','Refill work'),('claim_to_refill_start_ms','领取后至补槽开始','Claim to refill start'),('claim_to_replacement_ready_ms','领取后至替代槽 Ready','Claim to replacement Ready')]:
  v=x[k];rows.append([tr(c,e),f(v['median']),f(v['p95']),f(v['p99']),f(v['max'])])
 table(rows,[200,75,75,75,75])
 txt(tr('256 次补槽均在清理前完成；所有成功实例保留时为 256 running + 64 ready，共 320 个独立实例。总进程 PSS '+f(x['peak_product_pss_mib'])+' MiB，含专属控制面，不含大部分内核内存和未映射页缓存。','All 256 refills finish before cleanup. While retaining successes: 256 running + 64 ready, 320 independent instances. Product-process PSS '+f(x['peak_product_pss_mib'])+' MiB, including dedicated controllers but excluding most kernel memory/unmapped page cache.'))
 txt(tr('准备成本单列：服务启动至 64 槽就绪 '+f(x['deployment']['service_to_ready_ms']/1000)+' 秒；镜像模板准备、发布及首次创建 '+f(x['preparation']['template_prepare_publish_first_create_ms']/1000)+' 秒，未预先启动 Python。','Separate preparation: service start to 64 ready reserves '+f(x['deployment']['service_to_ready_ms']/1000)+' s; image-template preparation, publication and first create '+f(x['preparation']['template_prepare_publish_first_create_ms']/1000)+' s, without prestarting Python.'))
 txt(tr('验证通过：256 份独立 fsync 文件与网络身份；删除一半后其余仍可执行且文件正确；最终无用户实例残留且 64 槽就绪。额外真实 guest 验证父子继承进程继续运行、持久化 ext4/QCOW2 写入隔离和两种销毁顺序。','Passed: 256 independent fsynced files/network identities; survivors execute and retain files after half are deleted; final user inventory empty with 64 ready reserves. Additional real-guest tests verify inherited processes, persistent ext4/QCOW2 write isolation and both deletion orders.'))
 txt(tr('持久化、安全屏障和 CoW 保留。仅修改 113 的 sandbox_fork_staging；未触及 108。结果目录：/home/hong/src/research/pool-parallel-113。','Persistence, safety barriers and CoW retained. Only host 113 sandbox_fork_staging changed; host 108 untouched. Results: /home/hong/src/research/pool-parallel-113.'),'small')
SimpleDocTemplate(str(O/'fork-parallel-256-zh-en.pdf'),rightMargin=42,leftMargin=42,topMargin=36,bottomMargin=36,title='fork parallel refill / 256 concurrent creates').build(story)
