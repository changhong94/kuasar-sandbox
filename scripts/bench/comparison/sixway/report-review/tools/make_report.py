from pathlib import Path
import json,statistics as st,csv,html,hashlib
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
B=Path(__file__).parent;R=B/'results';assert (R/'complete.json').exists()
startup=json.loads((R/'startup/summary.json').read_text())
products=['kuasar-off','kuasar-uffd','kuasar-mlink','cube','agentenv','kuasar-fork'];names={'kuasar-off':'Kuasar off','kuasar-uffd':'Kuasar UFFD','kuasar-mlink':'mlink','cube':'CubeSandbox','agentenv':'AgentENV','kuasar-fork':'最新 fork'}
timing=[json.loads(p.read_text()) for p in (R/'timing').glob('[1-5]-*.json')];assert len(timing)==30
summary={}
for n in products:
 a=[d for d in timing if d['product']==n];assert len(a)==5
 assert all(d['success'] and not d['owned_remaining'] and all(x['success'] for x in d['pressure']) for d in a)
 q=dict(ready_ms=st.median(d['ready_ms'] for d in a),ready_max_ms=max(d['ready_ms'] for d in a),short_ms=st.median(st.median(d['short_ms']) for d in a),cpu_ms=st.median(d['cpu'][1] for d in a),io_ms=st.median(d['io'][1] for d in a),throughput=st.median(d['throughput'] for d in a))
 for k in ['pause_ms','resume_ms']:q[k]=st.median(d[k] for d in a) if all(d[k] is not None for d in a) else None
 d=json.loads((R/'growth'/f'{n}.json').read_text());assert d.get('verified')==50 and not d['owned'] and not d.get('error')
 levels={}
 for sample in d['samples']:levels[sample['instances']]=st.median(r['pss_mib'] for r in sample['resources'])
 arrays={}
 for mode in ['default','100','random']:
  z=json.loads((R/'arrays'/f'{n}-{mode}.json').read_text());assert z.get('success') and not z['owned'] and not z.get('error');arrays[mode]=dict(delta=z[mode]-z['python'],python=z['python'],loaded=z[mode])
 q['memory']=dict(levels=levels,delta_per_instance=(levels[50]-levels[0])/50,arrays=arrays);summary[n]=q
storage=[]
for p in (R/'timing/storage').glob('[1-3]-*.json'):
 d=json.loads(p.read_text());assert d['success'] and not d['remaining'];storage.append(d)
assert len(storage)==36
(R/'full-summary.json').write_text(json.dumps(summary,indent=2))
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'));font='STSong-Light';navy=colors.HexColor('#16324F')
styles={k:ParagraphStyle(k,fontName=font,fontSize=size,leading=lead,textColor=navy,spaceAfter=8,wordWrap='CJK') for k,size,lead in [('title',22,30),('h',14,21),('body',10,16),('small',8,12)]}
items=[]
def p(text,style='body'):items.append(Paragraph(text,styles[style]))
def page():items.append(PageBreak())
def tab(data,widths):
 t=Table([[Paragraph(html.escape(str(x)),styles['small']) for x in row] for row in data],colWidths=widths,repeatRows=1)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E4EDF5')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F6F8FA')]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.5,navy)]));items.extend([t,Spacer(1,10)])
def num(x):return 'N/A' if x is None else f'{x:.2f}'
stages=json.loads((R/'startup-stages.json').read_text())
p('113 六方基准：对齐套件口径','title')
p('2 vCPU · 2 GiB · 预备池 2 · 1 warmup + 50 次串行测量','h')
p('保留完整 exec、CPU/IO、存储和 50 实例内存套件。启动同时测量 native ready 与真实 Python print；请求开始和 stdout 接收终点均在客户端，包含解释器启动。')
tab([['产品','ready 中位 ms','Python 中位 ms','P95 ms','P99 ms','最大 ms']]+[[names[n]]+[num(stages[n]['native_ready_ms']['median'])]+[num(stages[n]['python_print_ms'][k]) for k in ['median','p95','p99','max']] for n in products],[95,86,90,76,76,76])
p('每方 50 次均须成功并完成销毁，warmup 单独保留为 00 号，不纳入统计。产品顺序逐轮轮换，没有择优、剔除长尾或只报最好一轮。P95/P99 为 nearest rank；50 个样本的 P99 等于最大值。')
p('原生 ready 来自同一条 exec 流中、启动 Python 前的 shell 随机标识；Python print 使用独立随机标识。它不是 API 返回，也不冒充服务端内部 guest-ready。')
p('基础镜像固定 digest','h');p('sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79','small')
p('六方均核对 2 vCPU、Python 3.12.14，以及 Python/libpython/libc/libcrypto 哈希。模板常驻命令使用原生 sleep 或 envd；准备阶段不启动 Python，不执行 Python 热集训练。warmup 和身份校验使用独立、随后销毁的沙箱，不回写模板。')
page();p('启动阶段与补槽成本','title')
tab([['产品','API 返回','exec→ready','ready→Python','内部 ready']]+[[names[n]]+[num(stages[n][k]['median'] if stages[n][k] else None) for k in ['api_ms','exec_to_native_ms','native_to_python_ms','internal_ready_ms']] for n in products],[115,96,96,96,96])
p('单位 ms，中位数。ready→Python 是两个客户端接收事件的间隔，含流缓冲/传输，不能解释为纯解释器 CPU 时间。服务端事件按沙箱 ID 关联，原始日志保留；不可观测项标 N/A。不同阶段可能嵌套，不可直接相加。')
tab([['产品','销毁中位 ms','补槽等待中位 ms','请求→删完并补满 ms']]+[[names[n],num(stages[n]['delete_ms']['median']),num(stages[n]['pool_after']['median'] if stages[n]['pool_after'] else None),num(stages[n]['lifecycle_through_refill_ms']['median']) if stages[n]['lifecycle_through_refill_ms'] else 'N/A'] for n in products],[115,128,128,128])
p('有池状态 API 的 mlink/fork 每次都检查 ready、assigned、preparing、模板存储和内存预热状态。删后补槽按 50 ms 轮询，延迟有该分辨率；服务端真实补槽执行时长另存事件。没有等价 API 的四方标 N/A，不能解释为零成本。')
prep=json.loads((R/'startup/client-preparation.json').read_text())
tab([['产品','客户端初始化 ms','初始池等待 ms','预备态 PSS MiB']]+[[names[n],num(prep[n]['client_preparation_ms']),num(prep[n]['initial_pool_gate']['elapsed_ms']) if prep[n]['initial_pool_gate']['supported'] else 'N/A',num(prep[n]['prepared_resources']['pss_mib'])] for n in products],[115,128,128,128])
p('完整镜像导入、模板构建、预热、服务准备的日志与失败尝试保存在 preparation 文件中。PSS 不含未映射宿主页缓存；mlink full-warm 还预读 2 GiB 模板内存。不能把单个分项当成完整准备总成本。')
page();p('内部阶段与准备分项','title')
phase=json.loads((R/'internal-phases-summary.json').read_text())
selected=[('kuasar-mlink','pico_restore.vmm_restore_ms','VMM 恢复'),('kuasar-mlink','pico_restore.guest_ready_ms','guest ready 等待'),('kuasar-mlink','thinkactor_create.durable_commit_ms','请求状态持久化'),('kuasar-fork','pool_assignment_save.elapsed_ms','槽位领取状态持久化'),('kuasar-fork','pool_lease.elapsed_ms','槽位领取总计'),('kuasar-fork','snapshot_bind.elapsed_ms','镜像绑定'),('kuasar-fork','refill.elapsed_ms','后台实际补槽'),('kuasar-fork','refill.replacement_ms','销毁至替代槽位就绪')]
tab([['产品 / 阶段','中位数 ms','最大 ms','样本']]+[[names[n]+' / '+label,num(phase[n]['phases'][k]['median']),num(phase[n]['phases'][k]['max']),phase[n]['phases'][k]['n']] for n,k,label in selected],[250,95,95,59])
p('领取总计包含持久化；内部恢复阶段也包含子阶段，不能重复求和。补槽执行时长与销毁到替代就绪的时间分开，后者含调度延迟。mlink 后台槽位与磁盘准备事件保存在 mlink-events.json。')
bg=json.loads((R/'mlink-background-summary.json').read_text())
tab([['mlink 后台分项','中位数 ms','最大 ms','事件数']]+[[k,num(v['median_ms']),num(v['max_ms']),v['events']] for k,v in bg.items()],[250,95,95,59])
p('后台事件按隔离实例的串行请求区间关联，每类均 50 个事件。runtime_slot_prepare_execution 包含 pico_slot_prepare，不能相加。磁盘准备不到 1 ms 并不意味着补满等待不到 1 ms；策略等待单列。')
page();p('模板准备成本','title')
template=json.loads((R/'template-preparation.json').read_text());mi=json.loads((R/'mlink-template.json').read_text());mw=json.loads((R/'mlink-prewarm.json').read_text());fp=json.loads((R/'startup/client-preparation.json').read_text())['kuasar-fork']['initial_pool_gate']['state']
pe=json.loads((R/'preparation-events.json').read_text())
tab([['准备项目','耗时 ms','边界'],['Kuasar off 重启至模板 ready',num(pe['kuasar-off']['restart_request_to_template_ready_ms']),'含停止旧服务和构建新模板，沿用镜像缓存'],['Kuasar UFFD 重启至模板 ready',num(pe['kuasar-uffd']['restart_request_to_template_ready_ms']),'含停止旧服务和构建新模板，沿用镜像缓存'],['AgentENV 导入至模板 ready',num(next(d['elapsed_ms'] for d in template if d['product']=='agentenv-template')),'客户端等待成功，不含之前失败尝试'],['mlink 导入至模板 ready',num(mi['elapsed_ms']),'2 CPU 新模板，不执行 Python'],['mlink 策略切换与预热',num(mw['elapsed_ms']),'关闭旧模板预热，预读新模板 2 GiB，准备 2 份磁盘'],['fork 2 槽位池填充',num(fp['preparation_ms']),'服务端池填充分项，不等于 seed/模板总准备'],['Cube 模板提交返回',num(next(d['elapsed_ms'] for d in template if d['product']=='cube-template')),'异步 PENDING，不能当作模板 ready 成本']],[165,92,242])
p('旧 registry 端口和隔离设备发布问题导致的准备重试保留在日志，未计入单次启动。off/uffd 使用服务端模板 ready 事件，而非 systemctl 返回。未取得可靠完整计时的准备项不伪造为零。')
rp=json.loads((R/'resource-profile-preparation.json').read_text());rr=json.loads((R/'resource-readiness.json').read_text())
p('后续完整套件扩池至 64：专属服务重置 '+num(rp['service_reset_ms'])+' ms，随后等待 fork 就绪和 mlink 预热 '+num(rr['elapsed_ms'])+' ms；这些属于资源测试准备，不计入容量 2 的启动统计。')
page();p('执行性能与生命周期','title')
tab([['产品','短 exec ms','CPU guest ms','32 MiB IO ms','并发2任务/s']]+[[names[n],num(summary[n]['short_ms']),num(summary[n]['cpu_ms']),num(summary[n]['io_ms']),num(summary[n]['throughput'])] for n in products],[115,90,98,100,96])
p('短 exec 为每轮 8 次 true 的客户端完成时间，取轮内中位数再取 5 轮中位数。CPU 为 SHA-256 处理 256 MiB 的 guest 墙钟时间。IO 包含确定性生成、哈希、写入和 fsync。吞吐包含创建、Python print、计算校验和销毁；它是容量 64 下的短突发指标，不是含补槽的长期稳态吞吐。启动专项另列销毁至补满成本。')
p('<b>IO 语义差异：</b>fork 当前业务文件写入 guest RAM overlay；fsync 不能赋予宿主断电后的持久化。因此不把 fork 的 IO 数字与持久化块盘排名，也不将其低磁盘增量解释为持久化存储优势。fork 控制状态和磁盘元数据的持久化屏障仍保留。')
p('完整套件内的创建与暂停/恢复（另 5 轮）','h')
tab([['产品','创建到print中位数 ms','最大值 ms','暂停 ms','恢复到print ms']]+[[names[n],num(summary[n]['ready_ms']),num(summary[n]['ready_max_ms']),num(summary[n]['pause_ms']),num(summary[n]['resume_ms'])] for n in products],[110,110,85,90,104])
p('这组创建值与第一页的 50 次启动专项分开保存，不合并样本。完整套件每轮还执行资源扫描和其他负载，缓存与调度条件不同。暂停/恢复使用产品正常持久化接口；恢复后再次启动 Python 输出随机标识，并校验写入文件的 SHA-256。')
p('最新 fork 不支持该持久化暂停/恢复 API，标为 N/A。保留内存的暂停不能替代持久化恢复。')
page();p('50 实例内存扩展','title')
tab([['产品','0实例 PSS MiB','50实例 PSS MiB','增量 MiB/实例']]+[[names[n],num(summary[n]['memory']['levels'][0]),num(summary[n]['memory']['levels'][50]),num(summary[n]['memory']['delta_per_instance'])] for n in products],[130,123,123,123])
p('PSS 包含各产品服务、seed/预备槽位和相关进程，按产品归属统计。每个观测点采 3 次取中位数；50 实例使用最后一次验证后的样本。增量为 (50实例−0实例)/50，不是每个 VM 的 RSS。PSS 不包含未映射的宿主页缓存、全部内核/设备开销，不能等同于宿主总内存成本；模板预热大小另列。')
p('扩展轨迹：PSS MiB','h')
tab([['产品','0','1','10','25','50']]+[[names[n]]+[num(summary[n]['memory']['levels'][k]) for k in [0,1,10,25,50]] for n in products],[114,77,77,77,77,77])
p('50 个并行 Python 进程的数组增量','h')
tab([['产品','零值 MiB','值100 MiB','随机值 MiB']]+[[names[n]]+[num(summary[n]['memory']['arrays'][m]['delta']) for m in ['default','100','random']] for n in products],[130,123,123,123])
p('每个进程持有 20 MiB bytearray；表中为全部 50 个进程的 PSS 增量，相对同组“Python 启动但不分配数组”的基线。仅在 50 个任务共同持有内存的时间窗口取样，至少 3 个有效样本；不是相对空 VM 的增量。')
page();p('双沙箱存储与共享','title')
def metric(n,diff,stage,key):
 vals=[]
 for d in storage:
  if d['product']!=n or bool(d['different'])!=diff:continue
  a=d['stages']['before'];z=d['stages'][stage]
  if z.get('supported') is False:continue
  if key=='extent':
   if a['extent']['valid'] and z['extent']['valid']:vals.append((z['extent']['unique_extent_bytes']-a['extent']['unique_extent_bytes'])/2**20)
  elif key=='allocated':vals.append((z['allocated_bytes']-a['allocated_bytes'])/2**20)
  else:vals.append(z['pss_mib']-a['pss_mib'])
 return st.median(vals) if vals else None
for diff in [False,True]:
 p(('不同内容' if diff else '相同内容')+'：两沙箱各写 32 MiB，3 轮中位数','h')
 tab([['产品','live物理增量 MiB','paused物理增量 MiB','live PSS增量 MiB']]+[[names[n],num(metric(n,diff,'live2','extent')),num(metric(n,diff,'paused2','extent')),num(metric(n,diff,'live2','pss'))] for n in products],[115,128,128,128])
p('物理占用由 FIEMAP extent 并集估计，避免把 reflink 共享 extent 重复计数。最新 fork 的数据与 SQLite 控制状态位于不同文件系统，分别求并集后相加。统计包含该产品所管理的模板、预备资源和控制状态；增量由同轮 before 基线扣除。')
p('所有写入都校验确定性摘要：同内容两沙箱摘要相同，不同内容摘要不同；支持者暂停/恢复后再次校验。N/A 表示接口不支持或 extent 无法可靠测量，不能视为零。fork 的 guest RAM 写入不会等量增加宿主持久化磁盘，不能据此给出磁盘去重优劣结论。')
p('完整 allocated bytes、PSS、extent 观测保存在 timing/storage/*.json 和 storage_measurements.csv；未用逻辑文件大小代替物理占用。','small')

page();p('口径与复现','title')
p('本轮对齐参考套件 startup-mode 的 CPU、内存、样本数、warmup 和池就绪准备方法；没有声称六方原生架构支持相同的六种缓存/恢复模式。mlink 使用 full-warm / L2 profile，fork 使用通用 CoW 槽位；其他产品维持原生模板恢复，不支持的池控制标 N/A。')
p('启动池容量为 2。启动测量完成后，因内存测试需要同时保有 50 个实例，mlink/fork 扩池至 64。扩池准备单列，后续资源指标属于该配置，不能拿来冒充容量 2 的预备开销。')
p('没有清空全局宿主页缓存，没有停止或修改其他用户任务。隔离 mlink 私有设备目录修复了设备节点发布竞态，并为模板导入预留块设备；VM ready 槽位数仍为 2。')
p('安全屏障、控制状态持久化和 CoW 保留。fork 的应用写入仍是 guest RAM overlay，持久化暂停/恢复标 N/A。所有 workload 摘要、独立生命周期及清理结果在 final-audit.json 中校验。')
audit=json.loads((R/'final-audit.json').read_text())
p('最终审计：300 次正式启动、6 次 warmup、30 组性能、240 个压力请求、36 组存储和 24 组内存案例全部通过；测试实例已清理。fork 保留 seed + 64 ready，assigned=0，seed FD 为 161→161。审计脚本先等后台补槽完成，再核对原生实例清单；没有重跑性能样本。')
p('主要证据','h');p('/home/hong/src/research/sixway-aligned-20261117','small')
tab([['文件','用途'],['tools/methodology.json / config.json','冻结口径、固定镜像及部署配置'],['results/startup/00-*.json','独立 warmup'],['results/startup/01-*.json … 50-*.json','300 个正式样本及前后资源池状态'],['results/startup-measurements.csv','完整逐样本时间'],['results/startup-stages.json','中位数、P95/P99、最大值'],['results/fork-events.log / mlink-events.json','服务端阶段事件，按 ID 关联'],['results/*preparation*.json / *prewarm*.json','准备、预热、扩池成本'],['results/timing / growth / arrays','完整补充套件原始数据'],['results/final-audit.json','正确性及清理审计']],[210,289])
def footer(c,d):
 c.setFont(font,8);c.drawString(42,23,'113 六方 | 50 次串行 | native ready + Python print');c.drawRightString(A4[0]-42,23,str(d.page))
output=B/'113-sixway-aligned-report.pdf';SimpleDocTemplate(str(output),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=38,bottomMargin=48,title='113 六方对齐套件基准报告').build(items,onFirstPage=footer,onLaterPages=footer);print(output)
