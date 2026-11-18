"""Unified bilingual report. Refuses incomplete or failed formal batches."""
from pathlib import Path
import sys,json,html,math,re,collections,statistics as st
from datetime import datetime,timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from reportlab.graphics.shapes import Drawing,Rect,Line,String,Circle
B=Path(sys.argv[1]);R=B/'results';O=B/'report';O.mkdir(exist_ok=True)
def load(p):return json.loads(p.read_text())
assert load(R/'matrix/complete.json')['samples_per_group']==50
assert load(B/'validation-batches-complete.json')
audit=load(B/'final-audit.json');assert audit['nested_host_stopped'] and not audit['merged'] and all(not r['public_instances'] for r in audit['products'].values())
assert load(B/'paced-complete.json')['complete']
import paced_charts as charts
bursts=charts.read(B)
paced={i:charts.read(B,i) for i in charts.INTERVALS}
failure_evidence=load(B/'failure-analysis.json')
assert all(r['client_rlimit_nofile'][0]>=8192 for r in bursts.values())
live=load(R/'live-formal/analyzed.json');resource=load(B/'resource-suite.json');pool=load(R/'pool-analysis.json')
identity=load(B/'image-verification.json');assert identity['all_18_verified'] and identity['same_interpreter_hash_within_each_language']
disk=load(B/'disk-backing-verification.json');assert len(disk['rows'])==2 and all(r['success'] for r in disk['rows']) and not disk['owned'] and not disk['pending']
nested_runtime=load(B/'nested-runtime-provenance.json');assert nested_runtime['sha256']==nested_runtime['copied_sha256']
recovery=load(B/'nested-recovery.json');assert recovery['all_passed']
assert all(r['post_restore_independent_writes'] and all(x['sqlite_after_restore'][0]=='ok' for x in r['sandboxes']) for r in recovery['runs'])
order=['kuasar-fork','kuasar-mlink','agentenv','cube','kuasar-off','kuasar-uffd']
names=dict(zip(order,['fork','mlink','AgentENV','CubeSandbox','Kuasar off','Kuasar UFFD']))
langs={'python':'Python','node':'Node.js','ruby':'Ruby'}
NAVY=colors.HexColor('#153550');BLUE=colors.HexColor('#3478a5');GREEN=colors.HexColor('#3a9076')
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'));story=[];english=False
styles={n:ParagraphStyle(n,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=s,leading=l,textColor=NAVY,spaceAfter=7,wordWrap='CJK') for n,s,l in [('title',19,26),('heading',12,18),('body',9.5,15),('small',7.7,11)]}
def tr(c,e):return e if english else c
def text(c,e=None,style='body'):story.append(Paragraph(c if e is None else tr(c,e),styles[style]))
def page(c,e):
 if story:story.append(PageBreak())
 text(c,e,'title')
def table(rows,widths=None):
 if widths is None:widths=[510/len(rows[0])]*len(rows[0])
 t=Table([[Paragraph(html.escape(str(v)),styles['small']) for v in row] for row in rows],colWidths=widths,repeatRows=1)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4edf4')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f4f7fa')]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEBELOW',(0,0),(-1,0),.4,NAVY)]));story.extend([t,Spacer(1,8)])
def stats(a):
 a=sorted(a);assert a
 return [st.median(a),a[math.ceil(.95*len(a))-1],a[math.ceil(.99*len(a))-1],a[-1]]
def f(v):return '—' if v is None else f'{v:,.2f}'
def group(p,l,m):
 a=[load(R/f'matrix/{l}/{p}/{m}/{i:02d}.json') for i in range(1,51)];assert all(x['success'] and x['destroyed'] for x in a);return a
def reference(p):return 'local_warm' if p=='kuasar-fork' else ('remote' if p in ('kuasar-off','kuasar-uffd') else 'product_default_warm')
def head(first):return [first,tr('指标 / ms','Metric / ms'),tr('中位数','Median'),'P95','P99',tr('最大值','Maximum')]
def metric_rows(label,a,keys=('ready_ms','print_ms')):
 return [[label,{'ready_ms':'Ready','print_ms':'print','snapshot_ms':tr('持久化暂停','Persistent pause'),'restore_api_ms':tr('恢复 API','Restore API')} .get(k,k)]+[f(v) for v in stats([x[k] for x in a])] for k in keys]
def relative(a,b):
 v=(a/b-1)*100
 return tr(f'fork 比 mlink {"高" if v>=0 else "低"} {abs(v):.1f}%',f'fork is {abs(v):.1f}% {"higher" if v>=0 else "lower"} than mlink')

def timeline(row,title):
 labels={'客户端':'Client','父 VM 暂停窗口':'Parent pause','父 VM':'Parent VM','子 VM':'Child VM','父 API':'Parent API','子 API':'Child API','控制面':'Control plane','服务端持久化':'Durable state','异步网络':'Async network'}
 events=row['spans'];lanes=list(dict.fromkeys(x['lane'] for x in events));end=max(row['print_ms'],max(x['end_ms'] for x in events))*1.04;left=105;w=395
 tracks=[]
 for lane in lanes:
  sub=[]
  for event in sorted((x for x in events if x['lane']==lane),key=lambda x:x['start_ms']):
   target=next((t for t in sub if t[-1]['end_ms']<=event['start_ms']),None)
   if target is None:target=[];sub.append(target)
   target.append(event)
  for i,track in enumerate(sub):tracks.append((lane,i,track))
 h=len(tracks)*24+80;d=Drawing(510,h)
 d.add(String(0,h-11,title,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=9,fillColor=NAVY))
 for i in range(6):
  x=left+w*i/5;d.add(Line(x,23,x,h-30,strokeColor=colors.HexColor('#dddddd'),strokeWidth=.4));d.add(String(x-8,10,f'{end*i/5:.0f}',fontName='Helvetica',fontSize=7))
 for i,(lane,track_no,track) in enumerate(tracks):
  y=h-67-i*24;label=labels[lane] if english else lane
  if track_no:label+=tr('（重叠）',' (overlap)')
  d.add(String(0,y+3,label,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=8))
  for e in track:
   x=left+e['start_ms']/end*w;ww=max(.6,e['duration_ms']/end*w);d.add(Rect(x,y,ww,13,fillColor=GREEN if lane=='父 VM 暂停窗口' else BLUE,strokeColor=colors.white,strokeWidth=.3))
   if ww>23:d.add(String(x+2,y+3,f"{e['duration_ms']:.1f}",fontName='Helvetica',fontSize=6,fillColor=colors.white))
 for key,color,yy in [('ready_ms','#bc4450',h-30),('print_ms','#6e4d9b',h-43)]:
  x=left+row[key]/end*w;d.add(Line(x,23,x,h-47,strokeColor=colors.HexColor(color),strokeWidth=1,strokeDashArray=[3,2]));d.add(Circle(x,h-62,3,fillColor=colors.HexColor(color),strokeColor=None))
  label=(tr('子 Ready','Child Ready') if key=='ready_ms' else tr('子 print','Child print'))+' '+f(row[key])+' ms'
  d.add(String(min(x-35,405),yy,label,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=8,fillColor=colors.HexColor(color)))
 d.add(String(455,0,tr('请求后 / ms','Since request / ms'),fontName=('Helvetica' if english else 'STSong-Light'),fontSize=7));story.append(d)

def pct(a,b):
 return '—' if a is None or b is None or a<0 or b<=0 else f'{(a/b-1)*100:+.1f}%'
def summary_page():
 page('结果摘要：fork 与 mlink','Results summary: fork versus mlink')
 text('统一镜像与客户端计时；串行指标为中位数，64 槽准备和 256 并发为各自单批次总耗时。百分比 = (fork / mlink - 1) × 100%；耗时和占用负值更好，吞吐正值更好。','Matching images and client boundaries. Serial metrics are medians; 64-slot preparation and 256-request completion each show one batch total. Difference = (fork / mlink - 1) × 100%. Negative is better for latency/footprint; positive is better for throughput.','small')
 rr=[[tr('项目','Measure'),'fork','mlink',tr('相对差异','Difference')]]
 def add(label,a,b,unit='ms'):rr.append([label+' / '+unit,f(a),f(b),pct(a,b)])
 for l in ('python','node'):
  for k in (('ready_ms','print_ms') if l=='python' else ('print_ms',)):
   add(langs[l]+' '+('Ready' if k=='ready_ms' else 'print'),st.median(x[k] for x in group('kuasar-fork',l,reference('kuasar-fork'))),st.median(x[k] for x in group('kuasar-mlink',l,reference('kuasar-mlink'))))
 a=resource['products']['kuasar-fork'];b=resource['products']['kuasar-mlink']
 add(tr('50 沙箱平均新增 PSS','Added PSS per instance at 50'),a['memory']['increment_per_instance'],b['memory']['increment_per_instance'],'MiB')
 add(tr('64 槽准备','Prepare 64 slots'),pool['fork']['preparation']['first_slot_start_to_64_ready_ms'],pool['mlink']['preparation']['first_slot_start_to_64_ready_ms'])
 aa=bursts['kuasar-fork']['print']['all_256_ms'];bb=bursts['kuasar-mlink']['print']['all_256_ms']
 add(tr('256 并发全部 print','All 256 concurrent prints'),aa/1000 if aa is not None else None,bb/1000 if bb is not None else None,'s')
 table(rr,[258,78,78,96])
 if any(row[-1]=='—' for row in rr[1:]):text('比例栏 — 表示没有完整可比值、基线非正或净增量为负；不把后台回收解释为节省百分比。','A dash in the ratio column means no complete comparison, a nonpositive baseline or a negative net increment; background reclamation is not presented as a savings percentage.',style='small')
 successes=', '.join(names[p]+' '+str(bursts[p]['print']['completed'])+'/256' for p in order)
 text(tr('256 同发完成率：','Simultaneous completion counts: ')+successes,style='small')
 agent=bursts['agentenv']['print']['all_256_ms']
 text(tr('AgentENV 的 256 请求总完成时间：','AgentENV all-256 completion time: ')+(f(agent/1000)+' s' if agent is not None else tr('未全部完成','incomplete'))+tr('。未全部成功的产品不参与“全部完成”速度排名；失败原因在并发章节说明。',' . Incomplete batches are excluded from all-complete speed rankings; failures are explained in the concurrency section.'),style='small')
 complete=[(r['print']['all_256_ms'],p) for p,r in bursts.items() if r['print']['all_256_ms'] is not None];best,p=min(complete)
 text(tr('本批次六方 256 同发全部完成最快的是 ','Fastest complete 256-request batch in this study: ')+names[p]+', '+f(best/1000)+tr(' s。',' s.'),style='small')
 better=[];worse=[]
 for row in rr[1:]:
  if row[-1]=='—':continue
  delta=float(row[-1].rstrip('%'));higher_good='task/s' in row[0]
  if delta==0:continue
  good=delta>0 if higher_good else delta<0
  (better if good else worse).append(row[0].split(' / ')[0]+' '+row[-1])
 text(tr('优势项：','Advantages: ')+('; '.join(better) or '—'),style='small')
 text(tr('不足项：','Disadvantages: ')+('; '.join(worse) or '—'),style='small')

def phase_table(row):
 lane_en={'客户端':'Client','父 VM 暂停窗口':'Parent pause','父 VM':'Parent VM','子 VM':'Child VM','父 API':'Parent API','子 API':'Child API','控制面':'Control','服务端持久化':'Durable state','异步网络':'Async network'}
 phase_en={'HTTP fork':'HTTP fork','SDK connect':'SDK connect','exec → Ready':'exec to Ready','解释器启动 → print':'Interpreter to print','暂停请求 → 恢复完成':'Pause request to resume','暂停/状态捕获':'Pause/capture state','线程退出/对象释放':'Host-thread quiescence','宿主 fork':'Host fork','复用 KVM / 恢复设备':'Reuse KVM/restore devices','屏障/等待/恢复运行':'Barrier/wait/resume','子进程 / KVM 初始化':'Child/KVM initialization','内存注册/vCPU/设备恢复':'Register RAM/restore vCPU/devices','线程就绪':'Threads ready','API 启动至绑定':'API start to bind','请求分发/暂停前准备':'Dispatch/pre-pause preparation','恢复后控制处理*':'Post-restore host handling','网络命名空间':'Network namespace','状态提交':'Commit state','网络完成 RPC':'Network-complete RPC'}
 rows=[[tr('泳道 / 阶段','Lane / phase'),tr('开始 ms','Start ms'),tr('结束 ms','End ms'),tr('实际耗时 ms','Elapsed ms')]]
 for x in row['spans']:
  rows.append([(lane_en[x['lane']]+' / '+phase_en[x['label']]) if english else x['lane']+' / '+x['label'],f(x['start_ms']),f(x['end_ms']),f(x['duration_ms'])])
 table(rows,[285,75,75,75])

for english in (False,True):
 styles={n:ParagraphStyle(n,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=size,leading=leading,textColor=NAVY,spaceAfter=7,wordWrap=('LTR' if english else 'CJK')) for n,size,leading in [('title',19,26),('heading',12,18),('body',9.5,15),('small',7.7,11)]}
 summary_page()
 page('113 六方沙箱综合报告','113 Six-Product Sandbox Report')
 text('统一正式批次 · 中文在前，英文在后','Unified formal batches · Chinese followed by English','heading')
 text('本报告以 fork 为主线，覆盖三语言启动、本地冷/热与 Manifest/chunk 恢复、运行中父沙箱 fork、执行、CPU/IO、存储、内存、持久化及槽位生命周期。启动、并发、资源和持久化测量来自本次 113 正式批次；隔离宿主重启功能验证单独标明范围。','This report centers on fork and covers three-language startup, local warm/cold and Manifest/chunk restoration, live-parent fork, execution, CPU/IO, storage, memory, persistence and pool lifecycle. Startup, concurrency, resources and persistence are measured in this formal study on host 113; isolated-host reboot validation is identified separately.')
 text('先读清楚 Ready 和 print','Read Ready and print correctly','heading')
 table([[tr('指标','Metric'),tr('起止点及含义','Boundary and meaning')],['API',tr('客户端调用创建或 HTTP fork 之前，到客户端收到响应；不代表 guest 已能执行。','Before the client create or HTTP fork call through its response; not proof of guest execution.')],['Ready',tr('同一起点，到客户端收到 shell 输出的随机 NATIVE 标识。证明命令通道与 shell 已能执行，不代表解释器已经就绪。','Same start through receipt of the shell-generated random NATIVE marker. Proves command/shell execution, not interpreter readiness.')],['print',tr('同一起点，到客户端收到 Python、Node.js 或 Ruby 输出的另一随机 READY 标识及换行。包含解释器启动、执行和输出传输。','Same start through receipt of a separate random READY marker and newline printed by Python, Node.js or Ruby. Includes interpreter startup, execution and output transport.')],[tr('父暂停','Parent pause'),tr('VMM pause_begin 到父 VM resume_done；另列全部 vCPU 停止后的窗口。不是客户端创建耗时。','VMM pause_begin through parent resume_done; the all-vCPUs-stopped window is also reported. Not client creation latency.')]], [76,434])
 text('shell 先输出 NATIVE 再 exec 解释器；客户端收到两行的间隔还受调度和输出传输影响，不能当作纯解释器 CPU 时间。两行可能在同一传输块到达。','The shell emits NATIVE before exec of the interpreter. The client-observed gap also includes scheduling/output transport and is not pure interpreter CPU time. Both lines may arrive in one transport chunk.','small')
 text('正式启动每组 1 次 warmup + 50 次串行测量；warmup 不计入统计。nearest-rank P95 为排序第 48 个，P99 等于第 50 个（最大值）。这些是本批次观察值，不代表生产长尾保证。','Each startup group has one excluded warmup and 50 serial measurements. Nearest-rank P95 is the 48th ordered sample; P99 is the 50th (maximum). These batch observations do not establish a production tail-latency guarantee.')
 text('部署：113，2 vCPU / 2 GiB，fork 与 mlink 均为 64 个通用槽位。准备与补槽均为 8 路，运行容量与预备池分开配置。','Deployment: host 113, 2 vCPU / 2 GiB, with 64 generic slots for both fork and mlink. Preparation and refill both use eight workers; running capacity is separate from the reserve pool.')
 page('测试模式、镜像与可比性','Modes, images and comparability')
 host=load(B/'host-current.json')
 text(tr('测试主机：','Test host: ')+host['host']+' / '+', '.join(host['cpu_models'])+' / '+str(host['logical_cpus'])+tr(' 个逻辑 CPU，',' logical CPUs, ')+f(host['memory']['MemTotal']/2**30)+' GiB RAM; Linux '+host['kernel'],style='small')

 table([[tr('模式','Mode'),tr('测试条件','Condition')],['local warm',tr('本地原生快照载体已驻留宿主页缓存；每次请求前用 mincore 验证。','Native local snapshot carriers resident in host page cache, verified with mincore before every request.')],['local cold',tr('相同原生载体，请求前验证数据页不驻留；只处理指定文件，不清空全机缓存。VM 池仍保持就绪。','Identical native carriers, verified nonresident before each request. Only selected files are conditioned; no global cache drop. VM slots remain ready.')],['remote',tr('Manifest/chunk 恢复，使用 RocksDB；分块、去重、压缩、加密/解密和内容验证均保留。remote 表示恢复路径，不表示跨地域网络。','Manifest/chunk restoration using RocksDB, retaining chunking, deduplication, compression, encryption/decryption and verification. Remote describes the path, not a cross-region network.')],[tr('运行中 fork','Live-parent fork'),tr('HTTP POST /sandboxes/{parent_id}/fork，继承当时运行中的状态；不是领取固定模板池的替代品。SDK 没有内建 parent.fork()。','HTTP POST /sandboxes/{parent_id}/fork inherits the running state at that moment; it is not a template-pool allocation. The SDK has no built-in parent.fork().')]], [95,415])
 for l in langs:
  a=group('kuasar-fork',l,'local_warm')[0];text(langs[l]+': '+a['image_digest'],style='small')
 text('每次使用新随机标识，同一 digest、解释器命令、root 用户与 /bin/bash -l -c。没有预先运行解释器，也没有语言专用预热。通用文件缓存策略仍是实现的一部分；local cold 不会清除快照内的 guest 页缓存。','Every request uses new random markers, matching digest, interpreter command, root user and /bin/bash -l -c. No interpreter is prestarted and no language-specific prewarming is used. Generic file-cache policy remains part of each implementation; local cold does not clear guest page cache saved in a snapshot.')
 text('mlink、AgentENV、CubeSandbox 只列已验证的默认预热参考，不把私有块缓存或 VM 池假装成可清空的普通文件缓存。','mlink, AgentENV and CubeSandbox appear only as validated default-warm references; private block caches and VM pools are not treated as ordinary file caches.')
 for l,label in langs.items():
  page(label+'：六方默认预热参考',label+': six-product default-warm reference')
  text('单位 ms。fork 使用 local warm；off/UFFD 使用产品的 Manifest/chunk 路径；其余为默认预热路径。不是六方严格同构的原生缓存实验。','Units: ms. fork uses local warm; off/UFFD use their Manifest/chunk path; others use default-warm paths. This is not a six-way identical native-cache experiment.')
  rr=[head(tr('对象','Product'))]
  for p in order:rr+=metric_rows(names[p],group(p,l,reference(p)))
  story.append(charts.bars([(names[p],st.median(x['ready_ms'] for x in group(p,l,reference(p))),st.median(x['print_ms'] for x in group(p,l,reference(p)))) for p in order],tr('Ready 与 print 中位数','Median Ready and print'),english,height=220))
  table(rr,[90,65,88,88,88,91])
  for k in ('ready_ms','print_ms'):
   a=st.median(x[k] for x in group('kuasar-fork',l,reference('kuasar-fork')));b=st.median(x[k] for x in group('kuasar-mlink',l,reference('kuasar-mlink')))
   text(('Ready' if k=='ready_ms' else 'print')+': '+relative(a,b))
  page(label+'：本地冷/热与 chunk 恢复',label+': local cache conditions and chunk restoration')
  text('单位 ms；图用对数刻度同时展示几十毫秒与数秒，百分比以数字计算。每组 50 次。','Units: ms; log scale shows tens of milliseconds and seconds together. Percentages use the numeric values. Fifty samples per group.',style='small')
  modes=('local_warm','local_cold','remote');ps=('kuasar-fork','kuasar-off','kuasar-uffd')
  labels={'local_warm':'warm','local_cold':'cold','remote':'chunk'}
  story.append(charts.bars([(names[p]+' / '+labels[m],st.median(x['ready_ms'] for x in group(p,l,m)),st.median(x['print_ms'] for x in group(p,l,m))) for m in modes for p in ps],tr('同一镜像，不同恢复路径','Same image, different restore paths'),english,log=True,height=295))
  rr=[[tr('对象 / 模式','Product / mode'),'Ready '+tr('中位','median'),'print '+tr('中位','median'),'print P95','print P99',tr('print 最大','print max')]]
  for m in modes:
   for p in ps:
    a=group(p,l,m);rr.append([names[p]+' / '+labels[m],f(st.median(x['ready_ms'] for x in a))]+[f(v) for v in stats([x['print_ms'] for x in a])])
  table(rr,[140,74,74,74,74,74])
  text(tr('按 print 中位数，fork 相对 UFFD：','fork relative to UFFD, median print: ')+', '.join(labels[m]+' '+f((st.median(x['print_ms'] for x in group('kuasar-fork',l,m))/st.median(x['print_ms'] for x in group('kuasar-uffd',l,m))-1)*100)+'%' for m in modes)+tr('（负数表示更短）。',' (negative means shorter).'),style='small')
  text('fork 的 remote 当前先完整重建稀疏原生载体，再走绑定/恢复；全部取 chunk、解密、落盘和同步都在创建计时内。off/UFFD 使用各自的恢复机制。不能把二者解释为相同按需缺页算法的比较。','fork remote currently reconstructs complete sparse native carriers before binding/restoring. Chunk fetch, decryption, file materialization and synchronization are all inside creation timing. off/UFFD use their own restoration mechanisms; this is not a comparison of identical demand-paging algorithms.','small')
 page('256 请求：容量与计时口径','256 requests: capacity and timing boundaries')
 text('每方分别测同时发送，以及每隔 10、25、50、100 ms 发送一次，共五批、每批 256 请求。每批另有 1 次排除的 warmup，所有成功实例保留至全部请求结束，核对存活后统一销毁。每个间隔只有一批实测，不把 256 个请求当作 256 轮独立突发。','Each product runs five batches: simultaneous dispatch and one request every 10, 25, 50 or 100 ms, 256 requests each. Each batch has one excluded warmup. All successful instances remain until every request settles, then undergo liveness checks and unified cleanup. Each interval has one observed batch, not 256 independent bursts.')
 text('64 槽是每批请求前实际核对的就绪量及配置基础目标，不是运行后空闲槽的硬上限。mlink 保留原生自适应策略，可临时扩大空闲池；每批开始前重新回到 64 个就绪槽。','The 64-slot baseline is verified before each batch and is the configured base target, not a hard cap on idle slots after requests begin. mlink retains native adaptive growth; each batch starts again from exactly 64 ready slots.',style='small')
 table([[tr('项目','Item'),tr('当前测试配置','Configuration')],[tr('fork / mlink 预备池','fork / mlink reserve'),tr('请求前 64 槽；准备和补槽 8 路','64 ready before requests; eight prep/refill workers')],['mlink',tr('总槽容量 320；等待队列 256；初始预备 64；镜像私有存储容量 320','320 total slots; 256 waiters; 64 initial reserves; private image storage capacity 320')],['off / UFFD',tr('各自 512 个网络端口；保留原生 runner 分配 5 秒超时','512 network ports each; native 5 s runner-assignment deadline retained')],['CubeSandbox',tr('320 实例逻辑容量，创建并发 256，API 限流 4096/s；640 vCPU / 640 GiB 为逻辑准入配额，不是物理扩容','320 logical instances, 256 concurrent creates, API limit 4096/s; 640 vCPU / 640 GiB are admission quotas, not added hardware')],[tr('客户端','Client'),tr('256 工作线程；FD 软上限 8192；创建超时 120 秒，首命令超时 90 秒','256 workers; FD soft limit 8192; create deadline 120 s, first-command deadline 90 s')]], [120,390])
 text('总完成时间：从统一屏障释放（第一个计划请求的时刻）到客户端收到最后一个 Python print。只有 256 个全部成功才给出该数值。单请求耗时从该请求实际调用创建开始；另外给出实际发送跨度和调度偏差。','Total completion runs from common barrier release (first scheduled request) through receipt of the last Python print, reported only when all 256 succeed. Per-request latency starts at that request’s actual create invocation. Actual dispatch span and scheduling lateness are reported separately.')
 text('10/25/50/100 ms 的计划发送跨度分别为 2.55/6.375/12.75/25.5 秒。这部分包含在总完成时间内，但不算作后发请求的服务处理耗时。所有路径仍包含新启动解释器。','Planned dispatch spans are 2.55/6.375/12.75/25.5 s for 10/25/50/100 ms. They are included in total completion, but not later requests’ own service latency. Every path includes launching a fresh interpreter.')
 table([[tr('发送间隔','Interval')]+[names[p] for p in order]]+[[str(i)+' ms']+[(f(paced[i][p]['print']['all_256_ms']/1000)+' s') if paced[i][p]['print']['all_256_ms'] is not None else str(paced[i][p]['print']['completed'])+'/256' for p in order] for i in charts.INTERVALS],[72,73,73,73,73,73,73])
 for interval in charts.INTERVALS:
  batch=paced[interval]
  page(tr(f'256 请求：间隔 {interval} ms 的结果',f'256 requests: {interval} ms spacing'),tr(f'256 请求：间隔 {interval} ms 的结果',f'256 requests: {interval} ms spacing'))
  rr=[[tr('对象','Product'),tr('print 成功','print count'),tr('全部完成 s','All complete s'),tr('调用跨度 s','Dispatch span s'),tr('单请求中位 ms','Request median ms'),tr('单请求最大 ms','Request max ms')]]
  for p in order:
   r=batch[p];lat=[(x['print_ns']-x['dispatch_ns'])/1e6 for x in r['requests'] if x['success']];rr.append([names[p],str(r['print']['completed'])+'/256',f(r['print']['all_256_ms']/1000) if r['print']['all_256_ms'] is not None else '—',f(r['client_dispatch_spread_ms']/1000),f(st.median(lat)) if lat else '—',f(max(lat)) if lat else '—'])
  table(rr,[88,67,85,85,93,92])
  aa=batch['kuasar-fork']['print']['all_256_ms'];bb=batch['kuasar-mlink']['print']['all_256_ms']
  if aa is not None and bb is not None:text(tr('全部完成：','All complete: ')+relative(aa,bb),style='small')
  text('单请求统计只包含成功 print，失败数量单独列出；不能据此将失败产品排为更快。发送调度会受客户端调度影响，原始记录保存每次实际调用时间。','Per-request statistics include only successful prints; failures are separate and cannot make an incomplete product rank as faster. Client scheduling affects actual dispatch; every invocation timestamp is retained.','small')
  story.append(charts.refill_chart(B,english,interval));refills=charts.refill_data(B,interval)
  table([[tr('对象','Product'),tr('清理前补槽数','Refills before cleanup'),tr('清理后补槽数','Refills after cleanup'),tr('实际工作中位 ms','Work median ms'),tr('最大 ms','Max ms')]]+[[names[p],refills[p]['during_retained_request_window'],refills[p]['after_cleanup_started'],f(refills[p]['median_work_ms']),f(refills[p]['max_work_ms'])] for p in ('kuasar-fork','kuasar-mlink')],[80,120,120,105,85])
  text('补槽横轴为第几次完成；纵轴为服务端记录的实际 VM 槽准备时间，不含策略等待。观察包含创建和最终清理，表格区分清理前后。mlink 可根据需求提高目标就绪量，因此完成数不一定恰好 256。','Refill x-axis is completion rank; y-axis is instrumented VM-slot preparation work, excluding policy wait. Observation includes creation and final cleanup, separated in the table. mlink may adapt its ready target to demand, so the count need not equal 256.','small')
  page(tr(f'间隔 {interval} ms：完成顺序与间隔',f'{interval} ms spacing: completion order and gaps'),tr(f'间隔 {interval} ms：完成顺序与间隔',f'{interval} ms spacing: completion order and gaps'))
  for drawing in charts.startup_charts(B,english,interval):story.append(drawing);story.append(Spacer(1,12))
  text('按客户端收到随机 Python print 的时刻排序。间隔图第 i 点 = 第 i 次完成 - 第 i-1 次完成，从第 2 次开始；失败没有完成点，不补零。图例为成功数 / 256。间隔越小只表示相邻完成更密集，不等于单请求越快。','Ordered by client receipt of random Python print markers. Gap i = completion i minus completion i-1, starting at rank 2. Failures have no completion point and are never zero-padded. Legend gives successes / 256. Smaller gaps mean denser completions, not necessarily lower per-request latency.','small')
 page('256 请求：失败原因与存活核查','256 requests: failure causes and retention checks')
 rr=[[tr('间隔 / 对象','Interval / product'),tr('失败数','Failures'),tr('服务端核对结果','Server-side finding')]]
 for r in failure_evidence:
  for reason in r['reasons']:rr.append([str(r['interval_ms'])+' ms / '+names[r['product']],reason['count'],tr(reason['cn'],reason['en'])])
 table(rr,[135,50,325])
 text('off/UFFD 的创建 API 可先返回 ID，再在后台启动。报告按同一 sandbox ID 关联服务端 launch terminal 与 runner_wait 日志，不把客户端 sandbox not found 本身当作根因。网络端口已扩容；runner 分配超时是本批次实测的独立瓶颈。','off/UFFD can return an ID before background startup finishes. Findings correlate the same sandbox ID with server launch-terminal and runner-wait events; client sandbox not found alone is not treated as a root cause. Expanded network ports do not remove the separately observed runner-assignment bottleneck.','small')
 if any(r['product']=='cube' and r['failed'] for r in failure_evidence):
  text('Cube 的 no more resource 说明调度器拒绝资源准入；日志未确认具体哪个资源项时，保持未确认，不写成纯启动慢，也不将同时出现的数据库死锁直接认定为该错误的原因。','Cube no more resource establishes scheduler admission refusal. If the exact limiting resource is not established, it remains unknown; it is not labeled slow startup, nor automatically attributed to concurrent database deadlocks.','small')
 assert all(not r['public_remaining'] and not r['owned_remaining'] and not r['cleanup_errors'] and r['cleanup_quiescence_verified'] for batch in paced.values() for r in batch.values())
 page('chunk 数据来源：按实际读取统计','Chunk payload sources: measured reads')
 text('不要求全部来自内存。普通索引/过滤器 Block Cache 命中不能证明 chunk 内容命中内存，因此本轮在真实 chunk Get 上采集线程级 RocksDB PerfContext，并单独记录后端命中。','An all-memory source is not required. Index/filter Block Cache hits do not prove that chunk payloads came from memory. This revision records thread-local RocksDB PerfContext for actual chunk Gets and tracks origin-store hits separately.')
 for unit in ('requests','bytes'):
  table_rows=[[tr('对象 / 语言','Product / language'),tr('内存 %','Memory %'),tr('文件 %','File %'),tr('后端 %','Origin %'),tr('未知 %','Unknown %')]]
  for l in ('python',):
   for p in ('kuasar-fork','kuasar-off','kuasar-uffd'):
    gg=group(p,l,'remote');tot={k:sum(x['remote_cache']['source_percentages']['categories'][k][unit] for x in gg) for k in ('memory','file','origin','unknown')};den=sum(tot.values());assert den>0
    table_rows.append([names[p]+' / '+langs[l]]+[f(100*tot[k]/den) for k in tot])
  text(tr('按成功读取次数加权' if unit=='requests' else '按返回的压缩/加密后字节数加权','Weighted by successful reads' if unit=='requests' else 'Weighted by returned encoded/encrypted bytes'),style='heading');table(table_rows,[150,90,90,90,90])
 text('50 次样本先合计分子/分母再求比例。重复读重复计数；零页/空洞不发起 chunk 读取，不计入分母。文件表示 RocksDB 读取载体文件，不必然是物理磁盘；无法区分内联内容与索引 IO 时归入未知。窗口为请求前至首次 print 命令完成、销毁之前。','Ratios are computed from summed numerators/denominators across 50 samples. Repeated reads count repeatedly; zero/hole ranges generate no reads and are excluded. File means a RocksDB file read, not necessarily physical device IO. Ambiguous inline-payload/index IO is unknown. The window ends after the first print command completes, before destruction.','small')
 page('chunk 来源观测范围与存储 IO','Chunk observation scope and storage IO')
 rr=[[tr('对象 / 语言','Product / language'),tr('每请求 chunk 读取次数中位','Median chunk Gets / create'),tr('返回编码字节中位 MiB','Median encoded payload / MiB'),tr('缓存进程 read_bytes 增量中位 MiB','Median cache-process read_bytes delta / MiB')]]
 for l in ('python',):
  for p in ('kuasar-fork','kuasar-off','kuasar-uffd'):
   a=group(p,l,'remote');rr.append([names[p]+' / '+langs[l],f(st.median(sum(v['requests'] for v in r['remote_cache']['source_percentages']['categories'].values()) for r in a)),f(st.median(sum(v['bytes'] for v in r['remote_cache']['source_percentages']['categories'].values()) for r in a)/2**20),f(st.median(r['remote_cache']['cache_daemon_disk_read_bytes'] for r in a)/2**20)])
 table(rr,[125,115,115,155])
 text('来源比例描述 chunk 内容在哪一层取得，而不是所有宿主内存/磁盘字节的精确归因。内存包括可确认的 RocksDB payload cache 或内存路径；文件类别不猜测底层缓存。本轮 RocksDB 配置启用 direct_reads，但仍单独给出内核记账 IO。','Source ratios identify the layer supplying chunk content, not a complete attribution of every host-memory/disk byte. Memory includes confirmed RocksDB payload-cache or in-memory paths; file reads do not guess lower-layer caching. RocksDB uses direct_reads in this deployment, while kernel-accounted IO is reported separately.')
 text('read_bytes 来自缓存进程 /proc/PID/io，包含该窗口内索引、过滤器、其他数据库读取和可能的后台 IO，不仅是 chunk payload。块对齐、压缩和额外元数据会让它与 payload 字节不同，不能直接相除宣称“物理磁盘来源百分比”。','read_bytes comes from the cache process /proc/PID/io and includes index/filter/other database reads and possible background IO, not only chunk payload. Block alignment, compression and metadata cause differences from payload bytes; dividing the two is not a valid physical-disk-source percentage.')
 page('快照载体大小与请求前缓存','Snapshot carrier size and pre-request residency')
 text('逻辑大小是当前有效载体的文件长度总和，包含稀疏空洞，不等于 guest 内存。实际磁盘占用按这些文件的 st_blocks×512 统计；跨文件共享块可能重复，不能替代后文 FIEMAP 去重统计。中间导出文件不计入。','Logical size is the sum of current carrier file lengths, including sparse holes; it is not guest RAM. Allocated storage uses st_blocks×512 for those files and may count shared extents repeatedly; the later FIEMAP accounting deduplicates extents. Intermediate exports are excluded.')
 capacity=load(B/'carrier-accounting.json')
 rr=[[tr('对象 / 语言','Product / language'),tr('逻辑 GiB','Logical GiB'),tr('占盘 GiB','Allocated GiB'),tr('warm 请求前驻留 GiB','Warm pre-request GiB'),tr('cold 请求前驻留 GiB','Cold pre-request GiB')]]
 for r in (v for v in capacity['rows'] if v['language']=='python'):rr.append([names[r['product']]+' / '+langs[r['language']]]+[f(r[k]/2**30) for k in ('logical_bytes','allocated_bytes','warm_resident_bytes','cold_resident_bytes')])
 table(rr,[134,85,85,103,103])
 text('“创建请求前的宿主页缓存驻留量”是 mincore 观察到的当前目标文件驻留页数×宿主页大小，并非应用 PSS。warm/cold 单独列出。fork 使用原生稀疏 RAM、基础盘、镜像盘和可写盘载体，逻辑总长度会大于压缩打包格式；各沙箱配置仍是 2 GiB RAM。','“Host page-cache residency before create” is mincore-resident target pages multiplied by host page size, not application PSS. Warm/cold are reported separately. fork uses sparse native RAM/base/image/writable-disk carriers, whose logical lengths can exceed compressed archives; each sandbox still has 2 GiB configured RAM.')
 for l,label in [('python','Python')]:
  g=live[l];page(label+'：从运行中父沙箱 fork',label+': fork from a running parent')
  labels={'parent_pause_ms':('父 VM 暂停','Parent VM pause'),'parent_all_vcpus_stopped_ms':('全部 vCPU 停止窗口','All vCPUs stopped'),'vcpu_quiesce_ms':('等待 vCPU 停止','Quiesce vCPUs'),'child_resume_ms':('请求到子 VM 恢复运行','Request to child VM resume'),'ready_ms':('请求到子 Ready','Request to child Ready'),'print_ms':('请求到子 print','Request to child print')}
  table([[tr('指标 / ms','Metric / ms'),tr('中位数','Median'),'P95','P99',tr('最大值','Maximum')]]+[[tr(*labels[k])]+[f(g['metrics'][k][n]) for n in ('median','p95','p99','max')] for k in labels],[190,80,80,80,80])
  text('每组 1 次 warmup + 50 次 HTTP fork。父沙箱已有运行进程和落盘文件；验证子继承进程状态、父子写入互不覆盖，并交替按父先/子先顺序独立销毁。父沙箱准备不计入 fork 请求，单列在原始记录。','Each group has one warmup and 50 HTTP forks from parents with running processes and persisted files. Tests verify inherited process state, independent writes and alternating parent-first/child-first destruction. Parent setup is outside the fork request and recorded separately.')
  timeline(g['representative'],tr('最接近 print 中位数的真实样本','Real sample closest to median print'))
  text('横轴以请求发出为 0；不同泳道允许重叠。条内数字是该条实际耗时，不把阶段中位数相加拼成虚构请求。宿主 CLOCK_MONOTONIC 为统一时间基准。','The request starts at time zero. Lanes may overlap; bar labels are actual span durations. Phase medians are not added into a fictional request. All host timestamps use CLOCK_MONOTONIC.','small')
  text('客户端：HTTP fork、连接、exec 到 Ready、解释器到 print。父 VM：暂停/捕获状态、宿主线程收束、fork、恢复运行。子 VM：KVM 初始化、内存注册与 vCPU/设备恢复、线程和安全屏障。控制面与持久化可与 VM 恢复重叠；异步网络也单独列出。','Client: HTTP fork, connection, exec-to-Ready, interpreter-to-print. Parent: pause/capture, host-thread quiescence, fork and resume. Child: KVM initialization, memory registration, vCPU/device restoration, threads and safety barriers. Control-plane and persistence spans can overlap VM restoration; asynchronous networking has its own lane.')
  text('图中的“恢复后控制处理”是连接、身份重置和宿主处理的合计区间，未独立打点的工作不伪造细分数字。guest 进度采样只验证持续运行，不拿采样间隔替代精确父暂停计时。','Post-restore control handling aggregates connection, identity reset and host processing. Uninstrumented internals are not assigned invented durations. Guest progress sampling verifies continuity; it does not replace exact host pause timestamps.')
  page(label+'：代表样本阶段明细',label+': representative-sample phase details')
  phase_table(g['representative'])
  text('各行是同一个真实请求的时间区间，可重叠，不能直接相加。Ready 与 print 的绝对位置同时标在时间图中。','Rows describe one real request and may overlap; do not add them. Absolute Ready and print positions are also marked on the timeline.','small')
  page(label+'：最长样本及阶段说明',label+': maximum sample and stage definitions')
  timeline(g['maximum'],tr('本组 print 最大值的真实样本','Real sample with maximum print latency'))
  phase_names={'暂停/状态捕获':'Pause / capture state','线程退出/对象释放':'Quiesce threads / release objects','宿主 fork':'Host fork','复用 KVM / 恢复设备':'Reuse KVM / restore devices','屏障/等待/恢复运行':'Barrier / wait / resume','子进程 / KVM 初始化':'Child / KVM initialization','内存注册/vCPU/设备恢复':'Register RAM / restore vCPU and devices','线程就绪':'Threads ready','请求分发/暂停前准备':'Dispatch / pre-pause preparation','恢复后控制处理*':'Post-restore control handling*','网络命名空间':'Network namespace','网络完成 RPC':'Network completion RPC','状态提交':'Durable state commit'}
  selected=[x for x in g['maximum']['spans'] if x['lane'] in ('父 VM','子 VM','控制面')]
  table([[tr('泳道 / 阶段','Lane / phase'),tr('开始 ms','Start ms'),tr('结束 ms','End ms'),tr('实际耗时 ms','Elapsed ms')]]+[[({'父 VM':'Parent','子 VM':'Child','控制面':'Control'}[x['lane']]+' / '+phase_names[x['label']]) if english else x['lane']+' / '+x['label'],f(x['start_ms']),f(x['end_ms']),f(x['duration_ms'])] for x in selected],[276,78,78,78])

 page('执行、CPU/IO 与并发任务','Execution, CPU/IO and concurrent tasks')
 rr=[[tr('对象','Product'),tr('短命令 ms','Short exec ms'),tr('SHA-256 ms','SHA-256 ms'),tr('32 MiB 写入任务 ms','32 MiB write task ms'),tr('同时处理 2 个任务时的完成速度（任务/秒）','Completion rate with 2 tasks at a time (tasks/s)')]]
 for p in order:
  r=resource['products'][p];rr.append([names[p]]+[f(r[k]) for k in ('short_ms','cpu_ms','io_ms','throughput')])
 table(rr,[95,90,90,125,110])
 text('全为本次最新代码、Python 镜像和持久化磁盘重跑。5 轮串行资源测试；短命令每轮 8 次 true，先求轮内中位数再取 5 轮中位数。它测 RPC、命令/进程启动与返回，不是纯 Python 启动。','Fresh runs use this revision, the Python image and persistent disks. Five serial resource rounds; each has eight true commands, summarized by the median of per-round medians. This measures RPC, command/process launch and return, not Python startup alone.')
 text('CPU：在 guest 内对 256 MiB 数据计算 SHA-256 的实际耗时，输入缓冲准备不计入；不是 CPU 使用率。IO：生成、哈希、写入 32 MiB 并 flush/fsync 的整体任务耗时，不是纯磁盘带宽。','CPU: guest elapsed time hashing 256 MiB with SHA-256, excluding input-buffer setup; not CPU utilization. IO: generating, hashing, writing and flush/fsync of 32 MiB as one task, not pure disk throughput.')
 text('这个指标表示：同时最多处理 2 个完整任务时，每秒能完成多少个任务。数值越高越好。','This measures how many complete tasks finish per second when at most two are processed at the same time. Higher is better.')
 text('一个任务包括：创建沙箱 → 启动 Python 并 print → 执行哈希计算 → 销毁沙箱。每轮共做 8 个任务，一个结束后再补下一个，直到全部完成。','One task consists of creating a sandbox, starting Python and printing, computing a hash, and deleting the sandbox. Each round has eight tasks. Whenever one finishes, the next begins, until all eight finish.')
 text('计算方法：8 个任务 ÷ 全部完成的实际耗时。例如整轮耗时 2 秒，完成速度就是 4 任务/秒。共测 5 轮，报告取 5 轮结果的中位数。','Calculation: 8 tasks divided by the elapsed time to finish all eight. For example, a two-second round gives 4 tasks/s. Five rounds are measured, and the reported value is their median.')
 text('它不是“同时运行两个命令”的速度，也不只是启动速度；创建、计算和销毁的耗时都包含在内。','This is not the speed of running two commands, nor startup speed alone: creation, computation and deletion are all included.')
 text('fork / mlink 中位数相对差异','Relative median differences: fork / mlink','heading')
 for key,label in [('short_ms',tr('短命令','Short exec')),('cpu_ms','SHA-256'),('io_ms',tr('32 MiB 写入任务','32 MiB write task')),('throughput',tr('同时处理 2 个任务时的完成速度（更高更好）','Completion rate with 2 tasks at a time (higher is better)'))]:
  text(label+': '+relative(resource['products']['kuasar-fork'][key],resource['products']['kuasar-mlink'][key]),style='small')
 page('两沙箱文件写入后的磁盘与内存增量','Disk and memory increments after two sandbox writes')
 for kind in ('same','different'):
  text(tr('两边写相同内容' if kind=='same' else '两边写不同内容','Identical content' if kind=='same' else 'Different content'),style='heading')
  rr=[[tr('对象','Product'),tr('运行时新增磁盘 MiB','Added disk, running / MiB'),tr('持久化暂停后新增磁盘 MiB','Added disk, saved / MiB'),tr('运行时新增进程 PSS MiB','Added PSS, running / MiB')]]
  for p in order:
   r=resource['products'][p]['storage'][kind];rr.append([names[p],f(r['live2']['extent_mib']),f(r['paused2']['extent_mib']),f(r['live2']['pss_mib'])])
  table(rr,[95,135,145,135])
  aa=resource['products']['kuasar-fork']['storage'][kind];bb=resource['products']['kuasar-mlink']['storage'][kind]
  text(tr('fork / mlink 相对差异：运行磁盘 ','fork / mlink differences: running disk ')+pct(aa['live2']['extent_mib'],bb['live2']['extent_mib'])+tr('，保存后磁盘 ','; saved disk ')+pct(aa['paused2']['extent_mib'],bb['paused2']['extent_mib'])+tr('，运行 PSS ','; running PSS ')+pct(aa['live2']['pss_mib'],bb['live2']['pss_mib']),style='small')
 text('基线：创建两个沙箱之前的产品所属目录与进程；两沙箱各写入并 fsync 32 MiB。每类 3 轮取中位数。磁盘统计按每个文件系统物理 extent 求并集，同一共享块只计一次，再跨文件系统求和；增量含实例和持久化元数据，不等于 64 MiB 用户文件本身。','Baseline: product-owned directories and processes before creating two sandboxes. Each writes and fsyncs 32 MiB. Three rounds per content case, median reported. Disk accounting unions physical extents within each filesystem, counts shared blocks once, then sums filesystems. Increments include instance/persistence metadata, not just the 64 MiB user payload.')
 text('PSS 为按共享比例分摊后的进程物理驻留内存，包含该产品专属控制面和缓存进程；不包含大多数内核内存或未映射文件页缓存。共享页面变化可能让某些增量接近零或为负，应按基线理解。','PSS proportionally charges shared resident process memory and includes dedicated control/cache processes. It excludes most kernel memory and unmapped file cache. Shared-page changes can make increments small or negative; interpret them relative to the stated baseline.','small')
 page('沙箱数量与进程物理内存','Sandbox count and resident process memory')
 rr=[[tr('对象 / PSS MiB','Product / PSS MiB'),'0','1','10','25','50',tr('新增/实例','Added / instance')]]
 for p in order:
  m=resource['products'][p]['memory'];rr.append([names[p]]+[f(m['levels'][str(n)]) for n in (0,1,10,25,50)]+[f(m['increment_per_instance'])])
 table(rr,[108,66,66,66,66,66,72])
 text('依次保留 0、1、10、25、50 个运行沙箱；每个水平取 3 次、间隔 1 秒的 PSS 中位数。0 不是空机：包含服务、模板和预备池。新增/实例 = (50 个时 - 0 个时)/50，不等于一个孤立 VM 的 RSS。','Retain 0, 1, 10, 25 and 50 running sandboxes. Each level uses the median of three PSS samples one second apart. Zero includes services, templates and ready pools, not an empty machine. Added/instance = (PSS at 50 - PSS at 0)/50, not an isolated VM RSS.')
 rr=[[tr('对象 / 50 个进程合计增量 MiB','Product / total increment for 50 processes / MiB'),tr('默认零数组','Default zero array'),tr('填充 100','Fill with 100'),tr('随机内容','Random content')]]
 for p in order:rr.append([names[p]]+[f(resource['products'][p]['memory']['arrays'][k]) for k in ('default','100','random')])
 table(rr,[210,100,100,100])
 text('每沙箱一个 Python 进程持有 20 MiB 数组，重叠持有期采样；基线是已经运行的 50 个 Python 进程。默认零数组可能利用共享零页、尚未逐页实际写入，不能与显式填充/随机写入视作同样物理提交量。','Each sandbox holds a 20 MiB array in a Python process; samples are taken during overlapping retention. Baseline is 50 already-running Python processes. Default zero arrays may use shared zero pages without explicit writes and are not equivalent to physically touching every page.')
 text('fork 的实际 guest 挂载信息已核对：可写目录位于 ext4 块设备，宿主使用可写 QCOW2；父子使用不同的可写磁盘，双向写入和两种销毁顺序均验证通过。','Actual guest mount information confirms that fork writes to an ext4 block device backed by writable host QCOW2. Parent and child have separate writable disks; independent writes and both destruction orders pass.')
 page('持久化快照：保存、恢复与磁盘增量','Persistent snapshots: save, restore and disk increment')
 rr=[head(tr('对象','Product'))];snap={}
 for p in order:
  a=[load(R/f'snapshots/{p}/{i:02d}.json') for i in range(1,51)];assert all(x['success'] and x['destroyed'] and x['process_state_verified'] and x['file_state_verified'] for x in a);snap[p]=a
  rr+=metric_rows(names[p],a,('snapshot_ms','ready_ms','print_ms'))
 table(rr,[95,80,83,83,83,86])
 for k,label in [('snapshot_ms',tr('持久化保存','Persistent save')),('ready_ms',tr('恢复到 Ready','Restore to Ready')),('print_ms',tr('恢复到 print','Restore to print'))]:
  text(label+': '+relative(st.median(x[k] for x in snap['kuasar-fork']),st.median(x[k] for x in snap['kuasar-mlink'])),style='small')
 text('每组 1 次 warmup + 50 次。保存前：运行中进程持有 32 MiB 随机内存、递增计数器和稳定 PID，并有 fsync 完成的 32 MiB 文件。保存计时为客户端发出持久化 pause 到 API 确认；源实例保持暂停。恢复计时为发出 resume/connect 到 shell Ready / 新启动 Python 的 print。','One warmup and 50 samples per product. Before saving, a process holds 32 MiB of random memory, an increasing counter and stable PID, alongside a fsynced 32 MiB file. Save timing is persistent-pause request through API acknowledgment; the source remains paused. Restore timing is resume/connect request through shell Ready or newly started Python print.','small')
 page('持久化结果的范围与验证','Persistence scope and verification')
 table([[tr('对象','Product'),tr('保存导致的磁盘增量中位 MiB','Median save-induced disk increment / MiB'),tr('最大 MiB','Maximum / MiB')]]+[[names[p],f(st.median(x['snapshot_disk_increment_bytes'] for x in snap[p])/2**20),f(max(x['snapshot_disk_increment_bytes'] for x in snap[p])/2**20)] for p in order],[130,250,130])
 text('磁盘基线是文件已写入、进程已运行但尚未请求保存时；结束点为保存确认后的产品目录 extent 观测。统计产品存储后端净增量，含元数据/并发回收影响，不把它冒充独立快照文件长度。','Disk baseline is after the file/process setup but before save. The endpoint is product-directory extent observation after save acknowledgment. This is net backend allocation including metadata/GC effects, not the length of an isolated snapshot file.')
 text('保存后为了观测磁盘会额外保持暂停，再显式恢复；这段人为观测等待不算保存或恢复耗时。恢复保留保存后的自然缓存，不代表断电后的冷启动。验证恢复后 PID 和内存摘要不变、计数器继续增长、文件摘要一致，并独立销毁。','Storage observation deliberately extends the paused interval before explicit resume; this wait is excluded from save/restore latency. Restores retain natural post-save caches and are not cold power-loss restores. Checks verify unchanged PID/memory digest, advancing counter and matching file digest, followed by independent destruction.')
 text('API 返回不单独证明所有产品的掉电持久化承诺。fork 的 fsync/原子发布及安全屏障保留；宿主重启恢复采用隔离嵌套宿主验证，物理 113 不重启。','API acknowledgment alone does not prove every product’s power-loss guarantee. fork retains fsync/atomic publication and safety barriers; host-restart recovery is validated in an isolated nested host, without rebooting physical host 113.')
 text('隔离宿主重启与 SQLite WAL 验证','Isolated host reboot and SQLite WAL validation','heading')
 text('独立功能验证批次的两轮真实嵌套 Linux 宿主重置，分别验证父先/子先销毁。运行中的 SQLite 连接使用 WAL + synchronous=FULL；事务计数与内存计数一致。恢复后保持进程 PID、内存秘密和递增状态，SQLite integrity_check 为 ok，父子文件写入独立；第二轮另验证恢复后再次 fork。','Two real nested-Linux host resets in the separately recorded functional-validation batch verify parent-first and child-first deletion. A live SQLite connection uses WAL + synchronous=FULL; transaction and in-memory counters agree. Restores preserve PID, an in-memory secret and progress, pass SQLite integrity_check, and retain independent parent/child writes. The second round also forks again after recovery.')
 page('64 槽准备、销毁与补满','64-slot preparation, deletion and refill')
 rr=[[tr('对象','Product'),tr('准备/补槽并发','Prep/refill workers'),tr('单槽中位 ms','Single-slot median ms'),tr('首槽开始到 64 槽完成 ms','First start to 64 ready / ms')]]
 for k in ('fork','mlink'):
  p=pool[k]['preparation'];assert p['concurrency']==8;rr.append([k,'8 / 8',f(p['single_slot_ms']['median']),f(p['first_slot_start_to_64_ready_ms'])])
 table(rr,[75,120,135,180])
 text('各取一次完整的首次填满记录，单槽取该次 64 个内部准备事件的中位数；总时间是首槽实际开始到第 64 槽就绪。并发工作有重叠，不能用总时间除以 64 当作单槽耗时。公共服务、模板与镜像导入不计入这项槽准备时间。','One complete initial-fill record is selected per product. Single-slot median uses its 64 internal preparation events; total spans the first actual start through the 64th ready slot. Work overlaps, so total divided by 64 is not single-slot latency. Common service/template/image import is outside this slot-preparation metric.')
 rr=[[tr('对象','Product'),tr('删除确认中位 ms','Delete ack median ms'),tr('删除后补满剩余等待中位 ms','Remaining full-pool wait / ms'),tr('实际补槽工作中位 ms','Actual refill work median ms')]]
 for p in ('kuasar-fork','kuasar-mlink'):
  r=next(x for x in pool['samples'] if x['product']==p and x['language']=='python');rr.append([names[p],f(r['delete_ms']['median']),f(r['remaining_full_pool_wait_after_delete_ms']['median']),f(r['slot_work_ms']['median'] if r['slot_work_ms'] else None)])
 table(rr,[90,125,160,135])
 text('使用 Python 默认预热路径的 50 次串行样本。删除确认是客户端发出删除到 API 返回；剩余等待从删除返回起，至无在用/准备中实例且 64 槽与当前镜像准备就绪。fork 在领取后就能补槽，故删除时可能已经补满；不把两者误写成“删除触发补槽”。','Uses 50 serial Python default-warm samples. Delete acknowledgment spans the client delete call through its response. Remaining wait ends when no instances are assigned/preparing and 64 slots plus the selected image are ready. fork can refill on claim and may already be full at deletion; this is not labeled deletion-triggered refill.')
 for k in ('delete_ms','remaining_full_pool_wait_after_delete_ms'):
  a=next(x for x in pool['samples'] if x['product']=='kuasar-fork')[k]['median'];b=next(x for x in pool['samples'] if x['product']=='kuasar-mlink')[k]['median'];text(tr('删除确认' if k=='delete_ms' else '补满剩余等待','Delete acknowledgment' if k=='delete_ms' else 'Remaining refill wait')+': '+relative(a,b),style='small')
 text('fork：领取持久化提交后立即释放预备池名额并唤醒补槽，没有正常路径的人为延迟；失败保留退避。mlink：保留 1000 ms 前台静默策略，用于减少后台准备对前台的争用；前台缺槽补充另有路径。该配置不是每次请求强制睡眠 1 秒。','fork immediately opens a reserve vacancy and wakes refill after durable assignment, without an artificial normal-path delay; failed preparations retain backoff. mlink retains a 1000 ms foreground-quiet policy to reduce background contention, with separate foreground deficit handling. It is not a compulsory one-second sleep per request.')
 page('补槽调度与 64 槽内存占用','Refill scheduling and memory at 64 ready slots')
 measure=next(r for r in pool['samples'] if r['product']=='kuasar-fork')['claim_to_refill_start_ms'];assert measure and measure['n']==50
 text(tr('fork 从持久化领取释放名额到补槽开始：中位 ','fork durable claim/vacancy to refill start: median ')+f(measure['median'])+' ms, P95 '+f(measure['p95'])+' ms, P99 '+f(measure['p99'])+tr(' ms。',' ms.'))
 memory=load(R/'pool-memory.json')
 table([[tr('64 槽就绪 / MiB','64 ready slots / MiB'),tr('槽进程 PSS 合计','Slot PSS total'),tr('每槽平均','Per-slot mean'),tr('公共进程 PSS','Common PSS')]]+[[names[p]]+[f(memory[p]['summary'][k]) for k in ('slot_processes_pss_mib','slot_processes_average_pss_mib','common_processes_pss_mib')] for p in ('kuasar-fork','kuasar-mlink')],[160,120,110,120])
 text('在本批次持久化测试完成后的空闲池观察 5 次，取中位数；与前文数量增长测试不是同一测量时点，不直接相减。槽进程为 64 个 VMM 及槽专属命名空间 holder；公共进程包含种子 VM、控制面和专属缓存/存储。PSS 按共享比例分摊，不含大多数内核内存或未映射页缓存。该表是 64 槽时的内存归属，不是从空池增加到满池的因果增量。','Median of five idle-pool observations after the persistence suite. This is a different measurement point from the earlier sandbox-count baseline; do not subtract the two. Slot processes include 64 VMMs and per-slot namespace holders; common processes include seed VM, control plane and dedicated caches/storage. PSS proportionally charges shared pages and excludes most kernel memory/unmapped file cache. This is attribution at 64 ready slots, not a causal empty-to-full increment.')
 text('两方预备池均为 64、准备和补槽均为 8 路。mlink 总槽容量为 320，其中初始 64 个预备槽，等待队列为 256；运行中的实例不会因 64 个初始预备槽而被限制为 64。容量上限与当前真实内存占用不是一回事。','Both start with 64 reserves and eight preparation/refill workers. mlink total slot capacity is 320, including the initial 64 reserves, with 256 waiters. The initial reserve is not a 64-running-instance limit. Admission capacity is distinct from physical memory usage.')

def footer(canvas,doc):
 canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(NAVY);canvas.drawString(42,25,'Host 113 | Six-product study | 2026-11');canvas.drawRightString(A4[0]-42,25,str(doc.page));canvas.restoreState()
class ReportDoc(SimpleDocTemplate):
 def afterFlowable(self,flowable):
  if isinstance(flowable,Paragraph) and flowable.style.name=='title':
   key='section-'+str(self.page)+'-'+str(len(getattr(self,'section_keys',[])))
   self.section_keys=getattr(self,'section_keys',[])+[key]
   self.canv.bookmarkPage(key);self.canv.addOutlineEntry(flowable.getPlainText(),key,level=0,closed=False)
ReportDoc(str(O/'sandbox-sixway-zh-en.pdf'),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=38,bottomMargin=40,title='Sandbox comparison / 六方沙箱综合报告',author='Benchmark study').build(story,onFirstPage=footer,onLaterPages=footer)
print(O/'sandbox-sixway-zh-en.pdf')
