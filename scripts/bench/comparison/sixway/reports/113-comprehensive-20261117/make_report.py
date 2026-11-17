from pathlib import Path
import json,html,statistics,hashlib,argparse
import pymupdf
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.graphics.shapes import Drawing,Rect,String
parser=argparse.ArgumentParser(description='Generate the Chinese six-product comprehensive report from verified batch A/B data.')
parser.add_argument('--batch-a',type=Path,required=True,help='Batch A results directory')
parser.add_argument('--batch-b',type=Path,required=True,help='Batch B root, containing results/ and tools/config.json')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
B=args.batch_b.resolve();R=B/'results';M=R/'matrix';O=args.output.resolve();O.mkdir(parents=True,exist_ok=True);H=args.batch_a.resolve()
import statistics as st
products=N if 'N' in globals() else []
N=['kuasar-fork','kuasar-mlink','kuasar-off','kuasar-uffd','cube','agentenv'];names={'kuasar-fork':'Kuasar fork','kuasar-mlink':'mlink','kuasar-off':'Kuasar off','kuasar-uffd':'Kuasar UFFD','cube':'CubeSandbox','agentenv':'AgentENV'}
L=['python','node','ruby'];ln=dict(zip(L,['Python','Node.js','Ruby']))
S={l:json.loads((M/l/'summary.json').read_text()) for l in L};T={l:json.loads((M/l/'startup-stages.json').read_text()) for l in L};F=json.loads((R/'fork-preparation.json').read_text());C=json.loads((B/'tools/config.json').read_text());A=json.loads((R/'final-audit.json').read_text());assert A['passed'] and A['measured_samples']==900
for l in L:
 for n in N:
  ds=[json.loads((M/l/f'{i:02d}-{n}.json').read_text()) for i in range(1,51)]
  assert all(d['success'] and d['destroyed'] and d['attempts']==1 for d in ds)
  assert abs(statistics.median(d['interpreter_print_ms'] for d in ds)-S[l][n]['median_ms'])<1e-8
font='STSong-Light';pdfmetrics.registerFont(UnicodeCIDFont(font));navy=colors.HexColor('#16324F');blue=colors.HexColor('#3687B9');green=colors.HexColor('#168578')
styles={k:ParagraphStyle(k,fontName=font,fontSize=size,leading=lead,textColor=navy,spaceAfter=6,wordWrap='CJK') for k,size,lead in [('title',22,29),('h',13,19),('body',10,15),('small',8,11)]};items=[]
def p(s,k='body'):items.append(Paragraph(s,styles[k]))
def page():items.append(PageBreak())
class DisplayNumber(str):
 def __new__(cls,value):
  obj=str.__new__(cls,f'{value:.2f}');obj.value=value;return obj
def num(v):return 'N/A' if v is None else DisplayNumber(v)
def tab(rows,widths,compare=True):
 t=Table([[Paragraph(html.escape(str(x)),styles['small']) for x in row] for row in rows],colWidths=widths,repeatRows=1)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E4EDF5')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F6F8FA')]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEBELOW',(0,0),(-1,0),.5,navy)]));items.extend([t,Spacer(1,10)])
 if compare:
  fr=next((r for r in rows[1:] if r[0]=='Kuasar fork'),None);mr=next((r for r in rows[1:] if r[0]=='mlink'),None)
  if fr is not None and mr is not None:
   differences=[]
   for label,fv,mv in zip(rows[0][1:],fr[1:],mr[1:]):
    if 'IO' in str(label):continue  # RAM overlay and durable block storage are not equivalent.
    try:
     fval,mval=getattr(fv,'value',float(fv)),getattr(mv,'value',float(mv))
     if mval<=0:continue
     differences.append(str(label)+f' {(fval/mval-1)*100:+.1f}%')
    except (ValueError,TypeError):continue
   if differences:p('fork 相对 mlink：'+'；'.join(differences)+'。','small')
def stage(l,n,k):
 d=T[l][n].get(k);return num(d['median']) if d else 'N/A'
p('113 六方沙箱综合基准报告','title');p('阅读口径：ready 和 print 分别测什么','h')
p('本报告按“定义与方法 → 启动结果 → 准备成本 → 执行及资源结果 → 生命周期与验证”组织。先说明计时含义，再展示性能数值；所有指标都明确所属测试批次。')
p('一次创建请求中的观测顺序','h')
tab([['时点','实际事件','含义'],['t0：开始','客户端调用 SDK/CLI 创建之前','两个启动指标共同的起点，包含客户端调用开销'],['tA：API 返回','创建调用返回 sandbox ID','控制面已返回；不保证首次命令已经可执行'],['tE：首次 exec','客户端提交同一条 shell 命令','连接建立或恢复等待都在后续时间内'],['tR：native ready','客户端收到 shell printf 输出的随机标识完整行','首次命令已在 guest 内执行，且输出已返回客户端；解释器尚不必就绪'],['tP：语言 print','客户端收到全新 Python / Node.js / Ruby 进程输出的另一随机标识完整行','解释器已启动并执行用户代码；不是 shell printf 冒充语言输出']],[90,210,195])
p('报告的两个主要启动指标','h')
p('<b>ready 延迟 = tR − t0。</b>本文的 ready 指客户端可观测的首次 shell 执行成功（native ready），不是服务端内部 VM-ready 时间，也不是 API 返回时间。')
p('<b>print 延迟 = tP − t0。</b>包含 ready 之前的全部等待，以及解释器启动、执行 print 和输出返回；解释器没有预先启动。Python 使用 print(..., flush=True)，Node.js 使用 process.stdout.write，Ruby 使用同步 stdout 的 puts。')
p('<b>ready→print = tP − tR。</b>两个接收事件之间的间隔包含解释器启动及输出传输/缓冲，并非纯解释器 CPU 时间；两个标识可能在同一次网络读取中到达。统计分位数不能跨阶段相加。')
p('另一种 ready：池中的 ready=2 是“两个预备槽位可领取”的状态条件，与上述延迟不同。native ready 也不承诺 CNI、外部网络或业务服务已就绪；本测试验证的是 guest 命令与输出通路。','small')
p('阅读重点：各结果表优先列出 fork 和 mlink，方便直接比较。百分比统一为 (fork / mlink − 1) × 100%；负值表示更少，正值表示更多。时间/资源占用越低越好，吞吐越高越好；不把负号一律解释为更好。分母为零、不支持或语义不等价的项目不计算。','small')
page();p('测试批次与覆盖矩阵','title')
p('批次 A：sixway-aligned-20261117。Python 完整套件，在 113 上完成；启动专项为 2 槽位，之后资源测试将 fork/mlink 扩池到 64。批次 B：sixway-languages-20261117。更新部署后的三语言启动专项，fork/mlink 池容量均为 2。两批均为每沙箱 2 vCPU / 2048 MiB。')
tab([['测试主题','批次 / 样本','语言与配置'],['启动、首次解释器 print','B：每方每语言 1 warmup + 50，合计 900 正式样本','Python、Node.js、Ruby；串行；池 2'],['短 exec、CPU、32 MiB IO','A：每方 5 轮；每轮 8 次短 exec','Python 模板；资源池 64'],['并发任务与吞吐','A：合计 240 个请求，任务并发 2','创建、Python、计算校验及销毁；短突发'],['暂停/恢复','A：每方 5 轮，支持者执行','恢复后 Python print 与文件摘要校验'],['内存增长与数组','A：24 组；0/1/10/25/50 实例 + 3 种数组模式','50 个 Python 进程；有效窗口至少 3 次观测'],['双沙箱存储','A：6 产品 × 2 内容模式 × 3 轮 = 36 组','各写 32 MiB；同内容/不同内容'],['独立运行、文件和销毁','B：18 组，每组两种销毁顺序','三语言；销毁一方后验证另一方'],['A 启动基线','每方 1 warmup + 50；共 300 正式样本','保留来源，不与 B 合并；主表采用 B']],[135,180,180])
p('覆盖说明','h');p('Node.js/Ruby 已覆盖启动、首次执行及独立销毁；CPU/IO、数组、存储负载仍是 Python 完整套件。没有把 Python 的资源结果改名为三语言结果，也没有宣称所有主题均在最新部署上重测。')
p('主机与批次可比性','h');p('113 主机为双路 Intel Xeon Gold 6161，44 物理核 / 88 逻辑 CPU，宿主内存约 376 GiB。B 的样本边界记录中，1 分钟 load 为 2.16–3.55（中位数 2.69）。未停止其他用户任务或清空全局缓存。')
p('A/B 的模板、预备池规模、缓存与部署时间不同，不用跨批次的时间差归因于代码优化。各项结论只对应表中批次。全文 N/A 表示接口不支持或没有可靠测量，不能当作零成本。')
page();p('统一口径与镜像身份','title');p('批次 B｜三语言启动专项','h')
tab([['项目','本轮约束'],['硬件与配置','113 真实 Linux guest；每沙箱 2 vCPU / 2048 MiB；fork、mlink 可配置预备池均为 2 槽位'],['采样','每语言每产品 1 warmup + 50 串行请求，逐轮轮换产品顺序；不重试、不裁剪长尾'],['起止点','调用 SDK/CLI 创建前 → 客户端收到解释器随机标识完整行；含 SDK/CLI、连接和解释器启动'],['统一执行','root 用户，/bin/bash -l -c；先输出独立 shell 随机标识，再 exec 对应解释器输出另一随机标识'],['准备与预热','模板常驻 sleep 或原生 agent，不执行语言专用训练；预检和 warmup 用一次性实例，不回写模板'],['缓存','fork 通用文件缓存上限 512 MiB/镜像；不是冷缓存测试。mlink 采用原生 full-memory 预热'],['统计','中位数；P95/P99 使用 nearest rank。50 个样本的 P99 等于最大值'],['环境保护','未清空全局缓存；未停止或修改其他用户进程。只调整本任务专属 fork/mlink 服务']],[95,400])
for l in L:
 q=C['_languages'][l];proof=json.loads((M/'preflight'/f'{l}-kuasar-fork.json').read_text());p(q['image']+' — '+proof['version'],'h');p(q['digest'],'small')
p('同语言的六方均验证解释器版本、SHA256、2 CPU 与约 2 GiB 内存一致。固定 digest 指原始 OCI 基础镜像；各产品仍需注入自己的 guest agent，最终磁盘文件不声称逐字节相同。完整镜像来源与解释器哈希见 image-provenance.json、matrix/preflight/*.json。','small')
p('版本：Kuasar 0b646f26dfdb；Cloud Hypervisor dd6fd577446f。部署二进制与本次构建产物 SHA256 一致。报告日期按客户端 2026-11-17；113 日志使用 CST，可能显示 2026-11-18。','small')
for l in L:
 page();p(ln[l]+'：ready 与 print 分布','title');p('批次 B｜每方 1 warmup + 50 串行；单位 ms；池容量 2','h')
 p('ready：创建请求 → 客户端收到 shell 随机标识','h')
 tab([['产品','中位','P95','P99','最大']]+[[names[n]]+[num(T[l][n]['native_ready_ms'][k]) for k in ['median','p95','p99','max']] for n in N],[119,94,94,94,94])
 p('print：创建请求 → 客户端收到新解释器随机标识','h')
 tab([['产品','中位','P95','P99','最大']]+[[names[n]]+[num(S[l][n][k]) for k in ['median_ms','p95_ms','p99_ms','max_ms']] for n in N],[119,94,94,94,94])
 p('阶段诊断：中位数（ms）','h')
 tab([['产品','API 返回','exec→ready','ready→print']]+[[names[n]]+[stage(l,n,k) for k in ['api_ms','exec_to_native_ms','native_to_interpreter_ms']] for n in N],[119,112,132,132])
 p('P95/P99 用 nearest rank；50 个样本的 P99 等于最大值。API 返回、客户端 ready、语言 print 是不同事件。阶段中位数不可直接相加得到总中位数；ready→print 包含输出缓冲/传输。','small')
page();p('请求后的销毁与补槽','title');p('批次 B｜各语言 50 次；中位数，单位 ms','h')
for l in L:
 p(ln[l]+'：不计入 ready / print 的请求后成本','h')
 tab([['产品','销毁','补满等待','创建→销毁并补满']]+[[names[n],stage(l,n,'delete_ms'),stage(l,n,'pool_after'),stage(l,n,'lifecycle_through_refill_ms') if n in ['kuasar-fork','kuasar-mlink'] else 'N/A'] for n in N],[119,112,132,132])
p('仅 mlink/fork 提供等价池状态 API；销毁后轮询到两个预备槽位可领取，再发起下一次请求。补满等待含调度和策略等待，不是后台补槽纯执行时间。其他产品标 N/A，不代表零成本。','small')
page();p('模板、缓存与准备成本','title');p('批次 B｜缓存输入；准备与请求计时分离','h')
rows=[['产品','Python 秒','Node.js 秒','Ruby 秒']]
for n in N:
 vals=[]
 for l in L:
  v=F['image_templates']['base' if l=='python' else l]['preparation_ms'] if n=='kuasar-fork' else json.loads((R/f'template-{n}-{l}.json').read_text())['elapsed_ms'];vals.append(num(v/1000))
 rows.append([names[n]]+vals)
tab(rows,[135,120,120,120]);p('各项为一次实测模板准备，不是 50 次分布。基于已有固定 digest 镜像缓存，不含首次联网下载；模板构建与正常启动是不同边界。Cube 等异步构建等待实际 ready，而不是仅测提交返回。','small')
p('fork 通用缓存与池准备','h')
tab([['语言','通用文件读取 MiB','缓存 RPC ms','宿主 RAM 预热 ms']]+[[ln[l],num(F['image_templates'][k]['metadata_cache']['regular_file_bytes_read']/2**20),num(F['image_templates'][k]['metadata_cache']['rpc_elapsed_ms']),num(F['image_templates'][k]['warmup_ms'])] for l,k in [('python','base'),('node','node'),('ruby','ruby')]],[105,130,130,130])
p('所有镜像使用同一通用规则，不按 Python/Node/Ruby 的二进制或模块名称筛选；application_executed=false。缓存会读入应用文件，因此本轮不是冷启动磁盘缓存测试。部分分项嵌套在模板准备时间中，不可重复相加。')
p('fork 服务启动到三个模板及池就绪：'+num(F['service_start_to_ready_ms']/1000)+' 秒；初始 2 槽位填充：'+num(F['pool']['preparation_ms'])+' ms。使用一个共享 VM 资源池，而非每种语言单独建 VM 池。')
p('mlink 模板导入后，每模板预热约 1.21 秒；每语言切换预热策略的实测成本分别为 '+ ' / '.join(num(json.loads((M/'preparation'/l/'policy-preparation.json').read_text())['elapsed_ms']/1000) for l in L)+' 秒（Python / Node.js / Ruby），单独记录，不计入请求延迟。')
p('准备期曾遇到 mlink 旧 64 份预热策略与新 2 槽位配置不匹配，已通过管理接口修正。失败尝试保留在 preparation.jsonl；表中正常导入成本不冒充包含部署排障的总耗时。','small')

products=N
timing=[json.loads(p.read_text()) for p in (H/'timing').glob('[1-5]-*.json')];assert len(timing)==30
summary={}
for n in products:
 a=[d for d in timing if d['product']==n];assert len(a)==5
 assert all(d['success'] and not d['owned_remaining'] and all(x['success'] for x in d['pressure']) for d in a)
 q=dict(ready_ms=st.median(d['ready_ms'] for d in a),ready_max_ms=max(d['ready_ms'] for d in a),short_ms=st.median(st.median(d['short_ms']) for d in a),cpu_ms=st.median(d['cpu'][1] for d in a),io_ms=st.median(d['io'][1] for d in a),throughput=st.median(d['throughput'] for d in a))
 for k in ['pause_ms','resume_ms']:q[k]=st.median(d[k] for d in a) if all(d[k] is not None for d in a) else None
 d=json.loads((H/'growth'/f'{n}.json').read_text());assert d.get('verified')==50 and not d['owned'] and not d.get('error')
 levels={}
 for sample in d['samples']:levels[sample['instances']]=st.median(r['pss_mib'] for r in sample['resources'])
 arrays={}
 for mode in ['default','100','random']:
  z=json.loads((H/'arrays'/f'{n}-{mode}.json').read_text());assert z.get('success') and not z['owned'] and not z.get('error');arrays[mode]=dict(delta=z[mode]-z['python'],python=z['python'],loaded=z[mode])
 q['memory']=dict(levels=levels,delta_per_instance=(levels[50]-levels[0])/50,arrays=arrays);summary[n]=q
storage=[]
for raw_path in (H/'timing/storage').glob('[1-3]-*.json'):
 d=json.loads(raw_path.read_text());assert d['success'] and not d['remaining'];storage.append(d)
assert len(storage)==36

page();p('执行性能与 CPU/IO','title');p('批次 A｜Python 模板；每方 5 轮；资源池 64','h')
tab([['产品','短 exec ms','CPU guest ms','32 MiB IO ms','并发2任务/s']]+[[names[n],num(summary[n]['short_ms']),num(summary[n]['cpu_ms']),num(summary[n]['io_ms']),num(summary[n]['throughput'])] for n in products],[115,90,98,100,96])
p('短 exec 为每轮 8 次 true 的客户端完成时间，取轮内中位数再取 5 轮中位数。CPU 为 SHA-256 处理 256 MiB 的 guest 墙钟时间。IO 包含确定性生成、哈希、写入和 fsync。吞吐包含创建、Python print、计算校验和销毁；它是容量 64 下的短突发指标，不是含补槽的长期稳态吞吐。启动专项另列销毁至补满成本。')
p('<b>IO 语义差异：</b>fork 当前业务文件写入 guest RAM overlay；fsync 不能赋予宿主断电后的持久化。因此不把 fork 的 IO 数字与持久化块盘排名，也不将其低磁盘增量解释为持久化存储优势。fork 控制状态和磁盘元数据的持久化屏障仍保留。')
page();p('生命周期：暂停、恢复与独立销毁','title');p('批次 A｜每方 5 轮；正常持久化接口','h')
tab([['产品','创建到print中位数 ms','最大值 ms','暂停 ms','恢复到print ms']]+[[names[n],num(summary[n]['ready_ms']),num(summary[n]['ready_max_ms']),num(summary[n]['pause_ms']),num(summary[n]['resume_ms'])] for n in products],[110,110,85,90,104])
p('A 的原始字段 ready_ms 实际以 Python print 为终点，本表已标作创建到 print，不属于 B 的 native ready。此组创建值与批次 B 的每组 50 次启动专项分开保存，不合并样本。完整套件每轮还执行资源扫描和其他负载，缓存与调度条件不同。暂停/恢复使用产品正常持久化接口；恢复后再次启动 Python 输出随机标识，并校验写入文件的 SHA-256。')
p('Kuasar fork（A） 不支持该持久化暂停/恢复 API，标为 N/A。保留内存的暂停不能替代持久化恢复。')
p('批次 B：三语言独立销毁验证','h');p('每产品每语言同时创建两个沙箱，写入不同内容；依次验证先销毁第一个和先销毁第二个两种顺序，幸存者继续读取自己的文件并执行新解释器。18 组均通过，两种顺序合计 36 组案例；不等价于断电或崩溃恢复验证。')
page();p('50 实例内存扩展','title');p('批次 A｜Python 模板；fork/mlink 预备池 64','h')
tab([['产品','0实例 PSS MiB','50实例 PSS MiB','增量 MiB/实例']]+[[names[n],num(summary[n]['memory']['levels'][0]),num(summary[n]['memory']['levels'][50]),num(summary[n]['memory']['delta_per_instance'])] for n in products],[130,123,123,123])
p('PSS 包含各产品服务、seed/预备槽位和相关进程，按产品归属统计。每个观测点采 3 次取中位数；50 实例使用最后一次验证后的样本。增量为 (50实例−0实例)/50，不是每个 VM 的 RSS。PSS 不包含未映射的宿主页缓存、全部内核/设备开销，不能等同于宿主总内存成本；模板预热大小另列。')
p('扩展轨迹：PSS MiB','h')
tab([['产品','0','1','10','25','50']]+[[names[n]]+[num(summary[n]['memory']['levels'][k]) for k in [0,1,10,25,50]] for n in products],[114,77,77,77,77,77])
p('50 个并行 Python 进程的数组增量','h')
tab([['产品','零值 MiB','值100 MiB','随机值 MiB']]+[[names[n]]+[num(summary[n]['memory']['arrays'][m]['delta']) for m in ['default','100','random']] for n in products],[130,123,123,123])
p('每个进程持有 20 MiB bytearray；表中为全部 50 个进程的 PSS 增量，相对同组“Python 启动但不分配数组”的基线。仅在 50 个任务共同持有内存的时间窗口取样，至少 3 个有效样本；不是相对空 VM 的增量。')
page();p('双沙箱存储与共享','title');p('批次 A｜同内容/不同内容，各 3 轮；每沙箱写入 32 MiB','h')
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
 tab([['产品','live物理增量 MiB','paused物理增量 MiB','live PSS增量 MiB']]+[[names[n],num(metric(n,diff,'live2','extent')),num(metric(n,diff,'paused2','extent')),num(metric(n,diff,'live2','pss'))] for n in products],[115,128,128,128],compare=False)
p('物理占用由 FIEMAP extent 并集估计，避免把 reflink 共享 extent 重复计数。Kuasar fork（A） 的数据与 SQLite 控制状态位于不同文件系统，分别求并集后相加。统计包含该产品所管理的模板、预备资源和控制状态；增量由同轮 before 基线扣除。')
p('存储表不列 fork 相对 mlink 的百分比：fork 的 RAM overlay 与持久化块盘语义不同，百分比会制造不成立的优劣比较。','small')
p('所有写入都校验确定性摘要：同内容两沙箱摘要相同，不同内容摘要不同；支持者暂停/恢复后再次校验。N/A 表示接口不支持或 extent 无法可靠测量，不能视为零。fork 的 guest RAM 写入不会等量增加宿主持久化磁盘，不能据此给出磁盘去重优劣结论。')
p('完整 allocated bytes、PSS、extent 观测保存在 timing/storage/*.json 和 storage_measurements.csv；未用逻辑文件大小代替物理占用。','small')


page();p('资源测试准备与最终验证','title')
p('批次 A：资源测试专属准备','h')
rp=json.loads((H/'resource-profile-preparation.json').read_text());rr=json.loads((H/'resource-readiness.json').read_text())
tab([['准备项目','实测时间','边界'],['2 槽位 → 64 槽位服务重置',num(rp['service_reset_ms'])+' ms','仅资源测试；不混入启动专项'],['随后等待池就绪与预热',num(rr['elapsed_ms'])+' ms','资源测试开始前完成']],[170,120,205])
p('批次 A 的内存、CPU/IO 与存储运行在扩池之后；其预备态资源不代表批次 B 的 2 槽位开销。PSS 与 FIEMAP 都有明确边界，不能从一个指标推断整机总内存或持久化能力。')
audit_a=json.loads((H/'final-audit.json').read_text());assert audit_a['complete'] and audit_a['all_workloads_verified'] and audit_a['all_owned_cleaned']
tab([['验证项目','批次 A','批次 B'],['启动与 warmup','300 正式 + 6 warmup','900 正式 + 18 warmup'],['执行/CPU/IO 性能','30 组通过','未重测；使用 A 正文数据'],['并发任务','240 请求通过','未做持续吞吐测试'],['存储 / 内存案例','36 / 24 组通过','未重测；使用 A 正文数据'],['独立销毁','套件清理与原生清单通过','18 组，两种销毁顺序均通过'],['最终保留资源','fork seed + 64 ready；assigned=0','可复用池保留；无已分配测试实例'],['FD 证据','fork seed：161 → 161','不据此声称长期 FD 压测通过']],[140,175,180])
p('安全与持久化语义','h');p('保留实现中的安全屏障、控制状态持久化与 CoW。A 的业务文件写入为 guest RAM overlay，fsync 不代表宿主断电后仍持久；不能以较低 IO 时间或磁盘增量宣称持久化存储优势。两批均未提供断电故障注入结果。B 的正确性证明限定于样本、文件隔离、独立执行和销毁。')
p('复现位置与代码','h')
p('批次 A：/home/hong/src/research/sixway-aligned-20261117<br/>批次 B：/home/hong/src/research/sixway-languages-20261117','small')
p('基准代码：changhong94/kuasar-sandbox，bench 分支 ca7dc03404d7。B 的实际运行脚本位于 sixway/hosts/113/tools/three-language-20261117；共享采样与语言定义位于 sixway/aligned。B 的 Kuasar / Cloud Hypervisor 构建提交及二进制哈希单独存档；该提交归属不追溯套用于 A。','small')
p('证据索引：B 的 matrix/*/startup-stages.json、逐样本 JSON、preflight、preparation.jsonl、independent-*.json 和 final-audit.json；A 的 timing/、timing/storage/、growth/、arrays/、resource-profile-preparation.json 与 final-audit.json。所有表直接读取 JSON 生成，未从 PDF 抄写数字。','small')
def footer(c,d):
 c.setFont(font,8);c.drawString(42,23,'113 六方综合基准 | 批次 A：完整资源套件 · B：三语言启动');c.drawRightString(A4[0]-42,23,str(d.page))
front=O/'body.tmp.pdf';SimpleDocTemplate(str(front),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=38,bottomMargin=48,title='113 六方沙箱综合基准报告（中文）',author='六方基准测试').build(items,onFirstPage=footer,onLaterPages=footer)
out=pymupdf.open(front)
titles=['113 六方沙箱综合基准报告','测试批次与覆盖矩阵','统一口径与镜像身份','Python：ready 与 print 分布','Node.js：ready 与 print 分布','Ruby：ready 与 print 分布','请求后的销毁与补槽','模板、缓存与准备成本','执行性能与 CPU/IO','生命周期：暂停、恢复与独立销毁','50 实例内存扩展','双沙箱存储与共享','资源测试准备与最终验证']
toc=[]
for i,pg in enumerate(out):
 text=pg.get_text()
 for title in titles:
  if title in text:toc.append([1,title,i+1])
assert len(toc)==len(titles),(len(out),toc)
out.set_toc(toc);out.set_metadata({'title':'113 六方沙箱综合基准报告（中文）','author':'六方基准测试','subject':'统一正文：三语言启动、执行、CPU/IO、存储、内存及生命周期；逐节标注批次 A/B'})
final=O/'113-sixway-comprehensive-report-zh.pdf';out.save(final,garbage=4,deflate=True)
manifest={'pdf':final.name,'pages':len(out),'sha256':hashlib.sha256(final.read_bytes()).hexdigest(),'batches':{'A':str(H),'B':str(R)},'sections':toc,'status':'final report authorized for publication'}
(O/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print(final,len(out),'pages')
front.unlink()
