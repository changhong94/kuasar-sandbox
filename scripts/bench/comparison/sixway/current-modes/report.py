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
from reportlab.graphics.shapes import Drawing,Rect,Line,String
B=Path(sys.argv[1]);R=B/'results';O=B/'report';O.mkdir(exist_ok=True)
def load(p):return json.loads(p.read_text())
assert load(R/'matrix/complete.json')['samples_per_group']==50
assert load(B/'validation-batches-complete.json')
audit=load(B/'final-audit.json');assert audit['nested_host_stopped'] and not audit['merged'] and all(not r['public_instances'] for r in audit['products'].values())
assert load(B/'burst256-complete.json')['retained_until_all_requests_settled']
import burst_charts
bursts=burst_charts.read(B)
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
styles={n:ParagraphStyle(n,fontName='STSong-Light',fontSize=s,leading=l,textColor=NAVY,spaceAfter=7,wordWrap='CJK') for n,s,l in [('title',19,26),('heading',12,18),('body',9.5,15),('small',7.7,11)]}
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
 events=row['spans'];lanes=list(dict.fromkeys(x['lane'] for x in events));end=max(x['end_ms'] for x in events);left=105;w=395
 tracks=[]
 for lane in lanes:
  sub=[]
  for event in sorted((x for x in events if x['lane']==lane),key=lambda x:x['start_ms']):
   target=next((t for t in sub if t[-1]['end_ms']<=event['start_ms']),None)
   if target is None:target=[];sub.append(target)
   target.append(event)
  for i,track in enumerate(sub):tracks.append((lane,i,track))
 h=len(tracks)*26+48;d=Drawing(510,h)
 d.add(String(0,h-11,title,fontName='STSong-Light',fontSize=9,fillColor=NAVY))
 for i in range(6):
  x=left+w*i/5;d.add(Line(x,23,x,h-30,strokeColor=colors.HexColor('#dddddd'),strokeWidth=.4));d.add(String(x-8,10,f'{end*i/5:.0f}',fontName='Helvetica',fontSize=7))
 for i,(lane,track_no,track) in enumerate(tracks):
  y=h-49-i*26;label=labels[lane] if english else lane
  if track_no:label+=tr('（重叠）',' (overlap)')
  d.add(String(0,y+3,label,fontName='STSong-Light',fontSize=8))
  for e in track:
   x=left+e['start_ms']/end*w;ww=max(.6,e['duration_ms']/end*w);d.add(Rect(x,y,ww,13,fillColor=GREEN if lane=='父 VM 暂停窗口' else BLUE,strokeColor=colors.white,strokeWidth=.3))
   if ww>23:d.add(String(x+2,y+3,f"{e['duration_ms']:.1f}",fontName='Helvetica',fontSize=6,fillColor=colors.white))
 d.add(String(455,0,tr('请求后 / ms','Since request / ms'),fontName='STSong-Light',fontSize=7));story.append(d)

for english in (False,True):
 page('113 六方沙箱综合报告','113 Six-Product Sandbox Report')
 text('统一正式批次 · 中文在前，英文在后','Unified formal batches · Chinese followed by English','heading')
 text('本报告以 fork 为主线，覆盖三语言启动、本地冷/热与 Manifest/chunk 恢复、运行中父沙箱 fork、执行、CPU/IO、存储、内存、持久化及槽位生命周期。全部测量来自本次 113 正式批次。','This report centers on fork and covers three-language startup, local warm/cold and Manifest/chunk restoration, live-parent fork, execution, CPU/IO, storage, memory, persistence and pool lifecycle. All measurements come from this formal study on host 113.')
 text('先读清楚 Ready 和 print','Read Ready and print correctly','heading')
 table([[tr('指标','Metric'),tr('起止点及含义','Boundary and meaning')],['API',tr('客户端调用创建或 HTTP fork 之前，到客户端收到响应；不代表 guest 已能执行。','Before the client create or HTTP fork call through its response; not proof of guest execution.')],['Ready',tr('同一起点，到客户端收到 shell 输出的随机 NATIVE 标识。证明命令通道与 shell 已能执行，不代表解释器已经就绪。','Same start through receipt of the shell-generated random NATIVE marker. Proves command/shell execution, not interpreter readiness.')],['print',tr('同一起点，到客户端收到 Python、Node.js 或 Ruby 输出的另一随机 READY 标识及换行。包含解释器启动、执行和输出传输。','Same start through receipt of a separate random READY marker and newline printed by Python, Node.js or Ruby. Includes interpreter startup, execution and output transport.')],[tr('父暂停','Parent pause'),tr('VMM pause_begin 到父 VM resume_done；另列全部 vCPU 停止后的窗口。不是客户端创建耗时。','VMM pause_begin through parent resume_done; the all-vCPUs-stopped window is also reported. Not client creation latency.')]], [76,434])
 text('shell 先输出 NATIVE 再 exec 解释器；客户端收到两行的间隔还受调度和输出传输影响，不能当作纯解释器 CPU 时间。两行可能在同一传输块到达。','The shell emits NATIVE before exec of the interpreter. The client-observed gap also includes scheduling/output transport and is not pure interpreter CPU time. Both lines may arrive in one transport chunk.','small')
 text('正式启动每组 1 次 warmup + 50 次串行测量；warmup 不计入统计。nearest-rank P95 为排序第 48 个，P99 等于第 50 个（最大值）。这些是本批次观察值，不代表生产长尾保证。','Each startup group has one excluded warmup and 50 serial measurements. Nearest-rank P95 is the 48th ordered sample; P99 is the 50th (maximum). These batch observations do not establish a production tail-latency guarantee.')
 text('部署：113，2 vCPU / 2 GiB，fork 与 mlink 均为 64 个通用槽位。代码在 sandbox_fork_staging；未修改 108 的优化分支。准备成本与启动请求内耗时分开列。','Deployment: host 113, 2 vCPU / 2 GiB, with 64 generic slots for both fork and mlink. Code is on sandbox_fork_staging; the 108 optimization branch is untouched. Preparation is reported separately from request latency.')
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
  table(rr,[90,65,88,88,88,91])
  for k in ('ready_ms','print_ms'):
   a=st.median(x[k] for x in group('kuasar-fork',l,reference('kuasar-fork')));b=st.median(x[k] for x in group('kuasar-mlink',l,reference('kuasar-mlink')))
   text(('Ready' if k=='ready_ms' else 'print')+': '+relative(a,b))
  page(label+'：本地冷/热与 chunk 恢复',label+': local cache conditions and chunk restoration')
  rr=[head(tr('对象 / 模式','Product / mode'))]
  for m in ('local_warm','local_cold','remote'):
   for p in ('kuasar-fork','kuasar-off','kuasar-uffd'):rr+=metric_rows(names[p]+' / '+m,group(p,l,m))
  table(rr,[110,45,88,88,88,91])
  text('fork 的 remote 当前先完整重建稀疏原生载体，再走绑定/恢复；全部取 chunk、解密、落盘和同步都在创建计时内。off/UFFD 使用各自的恢复机制。不能把二者解释为相同按需缺页算法的比较。','fork remote currently reconstructs complete sparse native carriers before binding/restoring. Chunk fetch, decryption, file materialization and synchronization are all inside creation timing. off/UFFD use their own restoration mechanisms; this is not a comparison of identical demand-paging algorithms.','small')
 page('同时创建 256 个 Python 沙箱','Simultaneous creation of 256 Python sandboxes')
 text('每方一次 256 请求突发批次，另有一次排除的 warmup。客户端 256 个工作线程在同一屏障后发起创建；成功实例全部保留，直到所有请求成功或失败后才统一销毁，不用提前删除腾槽。创建请求超时统一为 120 秒，首条命令超时 90 秒。','One 256-request burst per product, plus one excluded warmup. All 256 client workers start after a common barrier. Every created sandbox is retained until all requests succeed or fail; no early deletion frees slots. Create requests use a common 120-second timeout and the first command a 90-second timeout.')
 text('使用同一固定 digest 的 Python 镜像、相同 NATIVE / Python print 命令，以及各产品默认已准备路径。fork/mlink 请求前均有 64 个就绪槽；本组没有逐请求本地冷/热缓存处理。','Uses the same pinned Python image, NATIVE / Python print commands and prepared default product paths. fork/mlink each start with 64 ready slots. This burst does not apply per-request strict local cache conditioning.')
 rr=[[tr('对象','Product'),tr('API / Ready / print 成功数','API / Ready / print count'),tr('256 个全部 Ready / 秒','All 256 Ready / s'),tr('256 个全部 print / 秒','All 256 print / s'),tr('失败数','Failed')]]
 for p in order:
  r=bursts[p];rr.append([names[p],'/'.join(str(r[k]['completed']) for k in ('api','ready','print')),f(r['ready']['all_256_ms']/1000) if r['ready']['all_256_ms'] is not None else tr('未全部完成','Incomplete'),f(r['print']['all_256_ms']/1000) if r['print']['all_256_ms'] is not None else tr('未全部完成','Incomplete'),r['failed_requests']])
 table(rr,[95,135,110,110,60])
 rr=[[tr('对象','Product'),tr('成功部分最后 print / 秒','Last successful print / s'),tr('所有请求结束 / 秒（含失败）','All requests settled / s, including failures'),tr('客户端发起调用的跨度 / ms','Client dispatch spread / ms')]]
 for p in order:
  r=bursts[p];rr.append([names[p],f(r['print']['last_success_ms']/1000) if r['print']['last_success_ms'] is not None else '—',f(r['all_requests_settled_ms']/1000),f(r['client_dispatch_spread_ms'])])
 table(rr,[95,130,165,120])
 text('客户端使用 256 个工作线程，文件描述符软上限为 8192；该配置只作用于测试客户端及其 CLI 子进程，服务端配置保持不变。','The client uses 256 workers and an FD soft limit of 8192, applied only to the benchmark client and its CLI children. Service configurations are unchanged.','small')
 text('总完成时间从统一释放请求屏障计时，包含 SDK/CLI、服务排队与解释器启动。线程调用存在实测分发跨度，不声称网络包在同一纳秒抵达。未完成 256 个时不能把成功子集的最后时间写成全部完成时间。','Totals start at the common release barrier and include SDK/CLI overhead, server queues and interpreter startup. Client calls have a measured dispatch spread; packets are not claimed to arrive in one nanosecond. A successful subset’s final timestamp is not an all-256 completion time.','small')
 page('256 请求：失败范围与销毁核查','256 requests: failures and cleanup verification')
 rr=[[tr('对象','Product'),tr('失败阶段 / 客户端错误','Failure stage / client error'),tr('数量','Count')]]
 for p in order:
  counts=collections.Counter()
  for row in bursts[p]['requests']:
   if row['success']:continue
   message=row.get('error','')+' '+row.get('error_detail','');match=re.search(r'(?:HTTP\s+|^)([45][0-9]{2})(?:\s|:)',message)
   kind=('HTTP '+match.group(1)) if match else row.get('error_type','Unknown')
   counts[(tr('首次命令','First command') if row['api_success'] else tr('创建调用','Create call'))+' / '+kind]+=1
  if counts:
   for key,count in counts.most_common():rr.append([names[p],key,count])
  else:rr.append([names[p],tr('全部成功','All succeeded'),0])
 table(rr,[110,330,70])
 table([[tr('对象','Product'),tr('清理前确认存活','Alive before cleanup'),tr('存活检查失败','Failed retention checks'),tr('迟到实例 / 最终残留','Late / final remaining')]]+[[names[p],len(bursts[p]['retained_alive_before_cleanup']),len(bursts[p].get('retention_failed',[])),str(len(bursts[p]['unexpected_after_cleanup']))+' / '+str(len(bursts[p]['public_remaining']))] for p in order],[120,135,135,120])
 text('创建 API 返回 ID 不等于实例成功保留。存活检查失败表示全部请求结束时该实例已不存在或不可用，属于本次突发测试的观察结果，不标为通过。','An ID returned by create does not prove retention. A failed retention check means the instance was absent or unavailable after all calls settled; this is a measured burst outcome, not a passing validation.')
 text('失败分类按客户端实际错误记录。HTTP 503 本身不证明某个特定内部原因。客户端超时后服务端仍可能迟到发布实例：这些不算 print 成功，统一清理并持续核对实例清单与槽位就绪。','Failures are classified by observed client errors. HTTP 503 alone does not establish a specific internal cause. A server may publish an instance after the client times out; these are not print successes. They are deleted, with inventory and pool readiness checked until stable.')
 page('256 请求：完成顺序与相邻间隔','256 requests: completion order and adjacent intervals')
 for drawing in burst_charts.startup_charts(B,english):story.append(drawing);story.append(Spacer(1,12))
 text('每条线按客户端收到 Python print 的时间排序。间隔图第 i 个点 = 第 i 次完成时间 − 第 i−1 次完成时间，因此从第 2 次完成开始；失败不补零、不伪造完成点。颜色括号标出成功数 / 256。一次突发批次不是 50 次重复实验。','Each line is sorted by client receipt of Python print. Gap point i equals completion i minus completion i−1, starting at rank 2. Failures are not padded with zero gaps or fictional completion points. Legend counts show successes / 256. This is one burst, not 50 repeated bursts.','small')
 page('256 请求：fork 与 mlink 的补槽','256 requests: fork and mlink refill work')
 story.append(burst_charts.refill_chart(B,english));refills=burst_charts.refill_data(B)
 table([[tr('对象','Product'),tr('清理前完成的补槽数','Refills before cleanup'),tr('清理开始后完成的补槽数','Refills after cleanup starts'),tr('实际工作中位 ms','Median work ms'),tr('最大 ms','Maximum ms')]]+[[names[p],refills[p]['during_retained_request_window'],refills[p]['after_cleanup_started'],f(refills[p]['median_work_ms']),f(refills[p]['max_work_ms'])] for p in ('kuasar-fork','kuasar-mlink')],[80,125,135,85,85])
 text('横轴按补槽完成顺序编号；纵轴是服务器打点的 VM 槽实际准备耗时，不包含领取后的人为等待。观察窗口包括全部请求和结束后的统一清理，直到池重新达到 64 槽；表格区分清理前后。清理阶段的补槽不能解释成保留全部实例时已经补槽。','The x-axis orders refill completions; the y-axis is instrumented VM-slot preparation work, excluding policy wait. Observation spans the requests and final cleanup until 64 slots are ready again; the table separates phases. Cleanup-phase refill is not evidence of refill while all instances remain retained.')
 text('fork 当前容量计数包含已分配/退休中的实例。若 64 个实例占满容量，移除延迟也不会突破该上限；这与仅维持 64 个预备槽、另允许更多在用实例的设计不同。这里按当前实现实测，不为测试临时改变容量语义。','fork counts assigned/retiring instances toward capacity. Removing the delay does not bypass a full 64-instance limit. That differs from maintaining 64 spare slots while separately allowing more active instances. The test uses actual current semantics without changing them for the benchmark.')
 page('chunk 数据来源：按实际读取统计','Chunk payload sources: measured reads')
 text('不要求全部来自内存。普通索引/过滤器 Block Cache 命中不能证明 chunk 内容命中内存，因此本轮在真实 chunk Get 上采集线程级 RocksDB PerfContext，并单独记录后端命中。','An all-memory source is not required. Index/filter Block Cache hits do not prove that chunk payloads came from memory. This revision records thread-local RocksDB PerfContext for actual chunk Gets and tracks origin-store hits separately.')
 for unit in ('requests','bytes'):
  table_rows=[[tr('对象 / 语言','Product / language'),tr('内存 %','Memory %'),tr('文件 %','File %'),tr('后端 %','Origin %'),tr('未知 %','Unknown %')]]
  for l in langs:
   for p in ('kuasar-fork','kuasar-off','kuasar-uffd'):
    gg=group(p,l,'remote');tot={k:sum(x['remote_cache']['source_percentages']['categories'][k][unit] for x in gg) for k in ('memory','file','origin','unknown')};den=sum(tot.values());assert den>0
    table_rows.append([names[p]+' / '+langs[l]]+[f(100*tot[k]/den) for k in tot])
  text(tr('按成功读取次数加权' if unit=='requests' else '按返回的压缩/加密后字节数加权','Weighted by successful reads' if unit=='requests' else 'Weighted by returned encoded/encrypted bytes'),style='heading');table(table_rows,[150,90,90,90,90])
 text('50 次样本先合计分子/分母再求比例。重复读重复计数；零页/空洞不发起 chunk 读取，不计入分母。文件表示 RocksDB 读取载体文件，不必然是物理磁盘；无法区分内联内容与索引 IO 时归入未知。窗口为请求前至首次 print 命令完成、销毁之前。','Ratios are computed from summed numerators/denominators across 50 samples. Repeated reads count repeatedly; zero/hole ranges generate no reads and are excluded. File means a RocksDB file read, not necessarily physical device IO. Ambiguous inline-payload/index IO is unknown. The window ends after the first print command completes, before destruction.','small')
 page('chunk 来源观测范围与存储 IO','Chunk observation scope and storage IO')
 rr=[[tr('对象 / 语言','Product / language'),tr('每请求 chunk 读取次数中位','Median chunk Gets / create'),tr('返回编码字节中位 MiB','Median encoded payload / MiB'),tr('缓存进程 read_bytes 增量中位 MiB','Median cache-process read_bytes delta / MiB')]]
 for l in langs:
  for p in ('kuasar-fork','kuasar-off','kuasar-uffd'):
   a=group(p,l,'remote');rr.append([names[p]+' / '+langs[l],f(st.median(sum(v['requests'] for v in r['remote_cache']['source_percentages']['categories'].values()) for r in a)),f(st.median(sum(v['bytes'] for v in r['remote_cache']['source_percentages']['categories'].values()) for r in a)/2**20),f(st.median(r['remote_cache']['cache_daemon_disk_read_bytes'] for r in a)/2**20)])
 table(rr,[125,115,115,155])
 text('来源比例描述 chunk 内容在哪一层取得，而不是所有宿主内存/磁盘字节的精确归因。内存包括可确认的 RocksDB payload cache 或内存路径；文件类别不猜测底层缓存。本轮 RocksDB 配置启用 direct_reads，但仍单独给出内核记账 IO。','Source ratios identify the layer supplying chunk content, not a complete attribution of every host-memory/disk byte. Memory includes confirmed RocksDB payload-cache or in-memory paths; file reads do not guess lower-layer caching. RocksDB uses direct_reads in this deployment, while kernel-accounted IO is reported separately.')
 text('read_bytes 来自缓存进程 /proc/PID/io，包含该窗口内索引、过滤器、其他数据库读取和可能的后台 IO，不仅是 chunk payload。块对齐、压缩和额外元数据会让它与 payload 字节不同，不能直接相除宣称“物理磁盘来源百分比”。','read_bytes comes from the cache process /proc/PID/io and includes index/filter/other database reads and possible background IO, not only chunk payload. Block alignment, compression and metadata cause differences from payload bytes; dividing the two is not a valid physical-disk-source percentage.')
 page('快照载体大小与请求前缓存','Snapshot carrier size and pre-request residency')
 text('逻辑大小是当前有效载体的文件长度总和，包含稀疏空洞，不等于 guest 内存。实际磁盘占用按这些文件的 st_blocks×512 统计；跨文件共享块可能重复，不能替代后文 FIEMAP 去重统计。中间导出文件不计入。','Logical size is the sum of current carrier file lengths, including sparse holes; it is not guest RAM. Allocated storage uses st_blocks×512 for those files and may count shared extents repeatedly; the later FIEMAP accounting deduplicates extents. Intermediate exports are excluded.')
 capacity=load(B/'carrier-accounting.json')
 rr=[[tr('对象 / 语言','Product / language'),tr('逻辑 GiB','Logical GiB'),tr('占盘 GiB','Allocated GiB'),tr('warm 请求前驻留 GiB','Warm pre-request GiB'),tr('cold 请求前驻留 GiB','Cold pre-request GiB')]]
 for r in capacity['rows']:rr.append([names[r['product']]+' / '+langs[r['language']]]+[f(r[k]/2**30) for k in ('logical_bytes','allocated_bytes','warm_resident_bytes','cold_resident_bytes')])
 table(rr,[134,85,85,103,103])
 text('“创建请求前的宿主页缓存驻留量”是 mincore 观察到的当前目标文件驻留页数×宿主页大小，并非应用 PSS。warm/cold 单独列出。fork 使用原生稀疏 RAM、基础盘、镜像盘和可写盘载体，逻辑总长度会大于压缩打包格式；各沙箱配置仍是 2 GiB RAM。','“Host page-cache residency before create” is mincore-resident target pages multiplied by host page size, not application PSS. Warm/cold are reported separately. fork uses sparse native RAM/base/image/writable-disk carriers, whose logical lengths can exceed compressed archives; each sandbox still has 2 GiB configured RAM.')
 page('准备与发布成本','Preparation and publication costs')
 rr=[[tr('对象 / 语言','Product / language'),tr('原生快照导出 ms','Native export ms'),tr('只读镜像物化与验证 ms','Image materialization / verification ms')]]
 for p in ('kuasar-off','kuasar-uffd'):
  for r in load(B/(p+'-native.json')):rr.append([names[p]+' / '+langs[r['language']],f(r['publish_ms']),f(r['image_materialization_ms'])])
 table(rr,[160,150,200])
 text('原生快照导出：把 Manifest 表示的沙箱配置与执行快照发布成可恢复的本地文件。只读镜像物化与验证：把配置中的镜像引用也转成本地文件，并检查内容等价。它们发生在正式创建请求前，各执行一次，不是每次启动耗时。','Native export publishes Manifest-backed sandbox configuration and execution state as restorable local files. Image materialization also resolves read-only image references into local files and checks equivalence. These are one-time preparation operations before formal requests, not per-startup costs.')
 table([[tr('fork 模板','fork template'),tr('准备、发布并首次创建 ms','Prepare, publish and first create / ms')]]+[[langs[r['language']],f(r['create_with_template_publication_ms'])] for r in load(B/'fork-template-preparation.json')],[200,310])
 text('fork 此项包含通用镜像模板构建、Manifest 发布和一次验证性创建；命令为 /bin/sleep infinity，没有启动语言解释器。不把它称为单纯的 chunk 编码耗时。槽位自身的准备与补充见生命周期章节。','The fork figure includes generic image-template construction, Manifest publication and one validation create, running /bin/sleep infinity without starting a language interpreter. It is not labeled as chunk encoding alone. Slot preparation/refill is reported separately.')
 for l,label in langs.items():
  g=live[l];page(label+'：从运行中父沙箱 fork',label+': fork from a running parent')
  labels={'parent_pause_ms':('父 VM 暂停','Parent VM pause'),'parent_all_vcpus_stopped_ms':('全部 vCPU 停止窗口','All vCPUs stopped'),'vcpu_quiesce_ms':('等待 vCPU 停止','Quiesce vCPUs'),'child_resume_ms':('请求到子 VM 恢复运行','Request to child VM resume'),'ready_ms':('请求到子 Ready','Request to child Ready'),'print_ms':('请求到子 print','Request to child print')}
  table([[tr('指标 / ms','Metric / ms'),tr('中位数','Median'),'P95','P99',tr('最大值','Maximum')]]+[[tr(*labels[k])]+[f(g['metrics'][k][n]) for n in ('median','p95','p99','max')] for k in labels],[190,80,80,80,80])
  text('每组 1 次 warmup + 50 次 HTTP fork。父沙箱已有运行进程和落盘文件；验证子继承进程状态、父子写入互不覆盖，并交替按父先/子先顺序独立销毁。父沙箱准备不计入 fork 请求，单列在原始记录。','Each group has one warmup and 50 HTTP forks from parents with running processes and persisted files. Tests verify inherited process state, independent writes and alternating parent-first/child-first destruction. Parent setup is outside the fork request and recorded separately.')
  timeline(g['representative'],tr('最接近 print 中位数的真实样本','Real sample closest to median print'))
  text('横轴以请求发出为 0；不同泳道允许重叠。条内数字是该条实际耗时，不把阶段中位数相加拼成虚构请求。宿主 CLOCK_MONOTONIC 为统一时间基准。','The request starts at time zero. Lanes may overlap; bar labels are actual span durations. Phase medians are not added into a fictional request. All host timestamps use CLOCK_MONOTONIC.','small')
  text('客户端：HTTP fork、连接、exec 到 Ready、解释器到 print。父 VM：暂停/捕获状态、宿主线程收束、fork、恢复运行。子 VM：KVM 初始化、内存注册与 vCPU/设备恢复、线程和安全屏障。控制面与持久化可与 VM 恢复重叠；异步网络也单独列出。','Client: HTTP fork, connection, exec-to-Ready, interpreter-to-print. Parent: pause/capture, host-thread quiescence, fork and resume. Child: KVM initialization, memory registration, vCPU/device restoration, threads and safety barriers. Control-plane and persistence spans can overlap VM restoration; asynchronous networking has its own lane.')
  text('图中的“恢复后控制处理”是连接、身份重置和宿主处理的合计区间，未独立打点的工作不伪造细分数字。guest 进度采样只验证持续运行，不拿采样间隔替代精确父暂停计时。','Post-restore control handling aggregates connection, identity reset and host processing. Uninstrumented internals are not assigned invented durations. Guest progress sampling verifies continuity; it does not replace exact host pause timestamps.')
  page(label+'：最长样本及阶段说明',label+': maximum sample and stage definitions')
  timeline(g['maximum'],tr('本组 print 最大值的真实样本','Real sample with maximum print latency'))
  phase_names={'暂停/状态捕获':'Pause / capture state','线程退出/对象释放':'Quiesce threads / release objects','宿主 fork':'Host fork','复用 KVM / 恢复设备':'Reuse KVM / restore devices','屏障/等待/恢复运行':'Barrier / wait / resume','子进程 / KVM 初始化':'Child / KVM initialization','内存注册/vCPU/设备恢复':'Register RAM / restore vCPU and devices','线程就绪':'Threads ready','请求分发/暂停前准备':'Dispatch / pre-pause preparation','恢复后控制处理*':'Post-restore control handling*','网络命名空间':'Network namespace','网络完成 RPC':'Network completion RPC','状态提交':'Durable state commit'}
  selected=[x for x in g['maximum']['spans'] if x['lane'] in ('父 VM','子 VM','控制面')]
  table([[tr('泳道 / 阶段','Lane / phase'),tr('开始 ms','Start ms'),tr('结束 ms','End ms'),tr('实际耗时 ms','Elapsed ms')]]+[[({'父 VM':'Parent','子 VM':'Child','控制面':'Control'}[x['lane']]+' / '+phase_names[x['label']]) if english else x['lane']+' / '+x['label'],f(x['start_ms']),f(x['end_ms']),f(x['duration_ms'])] for x in selected],[276,78,78,78])

 page('执行、CPU/IO 与并发任务','Execution, CPU/IO and concurrent tasks')
 rr=[[tr('对象','Product'),tr('短命令 ms','Short exec ms'),tr('SHA-256 ms','SHA-256 ms'),tr('32 MiB 写入任务 ms','32 MiB write task ms'),tr('并发 2 任务/s','Concurrency 2 tasks/s')]]
 for p in order:
  r=resource['products'][p];rr.append([names[p]]+[f(r[k]) for k in ('short_ms','cpu_ms','io_ms','throughput')])
 table(rr,[95,90,90,125,110])
 text('全为本次最新代码、Python 镜像和持久化磁盘重跑。5 轮串行资源测试；短命令每轮 8 次 true，先求轮内中位数再取 5 轮中位数。它测 RPC、命令/进程启动与返回，不是纯 Python 启动。','Fresh runs use this revision, the Python image and persistent disks. Five serial resource rounds; each has eight true commands, summarized by the median of per-round medians. This measures RPC, command/process launch and return, not Python startup alone.')
 text('CPU：在 guest 内对 256 MiB 数据计算 SHA-256 的实际耗时，输入缓冲准备不计入；不是 CPU 使用率。IO：生成、哈希、写入 32 MiB 并 flush/fsync 的整体任务耗时，不是纯磁盘带宽。','CPU: guest elapsed time hashing 256 MiB with SHA-256, excluding input-buffer setup; not CPU utilization. IO: generating, hashing, writing and flush/fsync of 32 MiB as one task, not pure disk throughput.')
 text('并发 2：每轮 8 个完整任务，同时最多 2 个；每任务包含创建、实际 Python print、哈希工作和销毁。吞吐为成功任务数除以整轮实际耗时，最后取 5 轮中位数；不是无限时长稳态补槽吞吐。','Concurrency 2: eight complete tasks per round with at most two active. Each includes create, real Python print, hashing and deletion. Throughput is successes divided by whole-round elapsed time, then the median of five rounds; not indefinite steady-state refill throughput.')
 text('fork / mlink 中位数相对差异','Relative median differences: fork / mlink','heading')
 for key,label in [('short_ms',tr('短命令','Short exec')),('cpu_ms','SHA-256'),('io_ms',tr('32 MiB 写入任务','32 MiB write task')),('throughput',tr('并发任务吞吐（更高更好）','Task throughput (higher is better)'))]:
  text(label+': '+relative(resource['products']['kuasar-fork'][key],resource['products']['kuasar-mlink'][key]),style='small')
 page('两沙箱文件写入后的磁盘与内存增量','Disk and memory increments after two sandbox writes')
 for kind in ('same','different'):
  text(tr('两边写相同内容' if kind=='same' else '两边写不同内容','Identical content' if kind=='same' else 'Different content'),style='heading')
  rr=[[tr('对象','Product'),tr('运行时新增磁盘 MiB','Added disk, running / MiB'),tr('持久化暂停后新增磁盘 MiB','Added disk, saved / MiB'),tr('运行时新增进程 PSS MiB','Added PSS, running / MiB')]]
  for p in order:
   r=resource['products'][p]['storage'][kind];rr.append([names[p],f(r['live2']['extent_mib']),f(r['paused2']['extent_mib']),f(r['live2']['pss_mib'])])
  table(rr,[95,135,145,135])
 text('基线：创建两个沙箱之前的产品所属目录与进程；两沙箱各写入并 fsync 32 MiB。每类 3 轮取中位数。磁盘统计按每个文件系统物理 extent 求并集，同一共享块只计一次，再跨文件系统求和；增量含实例和持久化元数据，不等于 64 MiB 用户文件本身。','Baseline: product-owned directories and processes before creating two sandboxes. Each writes and fsyncs 32 MiB. Three rounds per content case, median reported. Disk accounting unions physical extents within each filesystem, counts shared blocks once, then sums filesystems. Increments include instance/persistence metadata, not just the 64 MiB user payload.')
 text('PSS 为按共享比例分摊后的进程物理驻留内存，包含该产品专属控制面和缓存进程；不包含大多数内核内存或未映射文件页缓存。共享页面变化可能让某些增量接近零或为负，应按基线理解。','PSS proportionally charges shared resident process memory and includes dedicated control/cache processes. It excludes most kernel memory and unmapped file cache. Shared-page changes can make increments small or negative; interpret them relative to the stated baseline.','small')
 page('沙箱数量与进程物理内存','Sandbox count and resident process memory')
 rr=[[tr('对象 / PSS MiB','Product / PSS MiB'),'0','1','10','25','50',tr('新增/实例','Added / instance')]]
 for p in order:
  m=resource['products'][p]['memory'];rr.append([names[p]]+[f(m['levels'][str(n)]) for n in (0,1,10,25,50)]+[f(m['increment_per_instance'])])
 table(rr,[108,66,66,66,66,66,72])
 text('依次保留 0、1、10、25、50 个运行沙箱；每个水平取 3 次、间隔 1 秒的 PSS 中位数。0 不是空机：包含服务、模板和预备池。新增/实例 = (50 个时 − 0 个时)/50，不等于一个孤立 VM 的 RSS。','Retain 0, 1, 10, 25 and 50 running sandboxes. Each level uses the median of three PSS samples one second apart. Zero includes services, templates and ready pools, not an empty machine. Added/instance = (PSS at 50 − PSS at 0)/50, not an isolated VM RSS.')
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
 text('本次两轮真实嵌套 Linux 宿主重置，分别验证父先/子先销毁。运行中的 SQLite 连接使用 WAL + synchronous=FULL；事务计数与内存计数一致。恢复后保持进程 PID、内存秘密和递增状态，SQLite integrity_check 为 ok，父子文件写入独立；第二轮另验证恢复后再次 fork。','Two fresh real nested-Linux host resets verify parent-first and child-first deletion. A live SQLite connection uses WAL + synchronous=FULL; transaction and in-memory counters agree. Restores preserve PID, an in-memory secret and progress, pass SQLite integrity_check, and retain independent parent/child writes. The second round also forks again after recovery.')
 page('64 槽准备、销毁与补满','64-slot preparation, deletion and refill')
 rr=[[tr('对象','Product'),tr('准备并发','Prep concurrency'),tr('单槽中位 ms','Single-slot median ms'),tr('首槽开始到 64 槽完成 ms','First slot start to 64 complete / ms')]]
 for k in ('fork','mlink'):
  p=pool[k]['preparation'];rr.append([k,p['concurrency'],f(p['single_slot_ms']['median']),f(p['first_slot_start_to_64_ready_ms'])])
 table(rr,[95,100,135,180])
 text('单槽是服务内部实际准备工作计时，不是总时间除以 64。总时间是首槽开始至首批 64 个就绪，公共服务与镜像准备另计；两个实现的准备并发不同，表中明确列出。','Single-slot time is instrumented preparation work, not total divided by 64. Total spans first-slot start through the first 64 ready slots, excluding common service/image setup. Preparation concurrency differs and is shown explicitly.')
 rr=[[tr('对象 / 语言','Product / language'),tr('删除确认中位 ms','Delete acknowledgment median ms'),tr('删除后补满剩余等待中位 ms','Remaining full-pool wait after delete / ms'),tr('实际补槽工作中位 ms','Actual refill work median ms')]]
 for l in langs:
  for p in ('kuasar-fork','kuasar-mlink'):
   r=next(x for x in pool['samples'] if x['product']==p and x['language']==l);rr.append([names[p]+' / '+langs[l],f(r['delete_ms']['median']),f(r['remaining_full_pool_wait_after_delete_ms']['median']),f(r['slot_work_ms']['median'] if r['slot_work_ms'] else None)])
 table(rr,[120,125,145,120])
 text('删除确认：客户端发出删除到 API 返回；不把异步清理假装成全部回收完成。补满剩余等待：从删除返回后开始轮询，至无分配/准备中的实例且 64 槽及选定镜像准备就绪。实际补槽工作来自服务器事件，和等待时间不是一个指标。','Delete acknowledgment spans client delete through API response; asynchronous cleanup is not mislabeled as completed reclamation. Remaining refill wait starts after delete response and ends when 64 slots and selected-image resources are ready with no assigned/preparing instances. Actual refill work comes from server events and is a separate metric.')
 text('fork 正常补槽没有人为延迟：销毁安全地、持久化地释放容量后，通过条件变量立即唤醒补槽线程。只有准备失败才保留重试退避。mlink 仍使用自己的 1000 ms 前台静默策略；本轮没有改变它。','fork has no artificial normal-path refill delay. Safe, durable capacity release immediately notifies the refill worker. Only failed preparation retains retry backoff. mlink retains its own 1000 ms foreground-quiet policy, unchanged in this revision.')
 page('补槽调度与 64 槽内存占用','Refill scheduling and memory at 64 ready slots')
 for l in langs:
  measure=next(r for r in pool['samples'] if r['product']=='kuasar-fork' and r['language']==l)['retirement_to_refill_start_ms']
  assert measure and measure['n']==50
  text(langs[l]+': '+tr('释放容量到补槽开始：中位 ','Capacity release to refill start: median ')+f(measure['median'])+' ms, P99 '+f(measure['p99'])+' ms',style='small')
 memory=load(R/'pool-memory.json')
 table([[tr('64 槽就绪时 / MiB','At 64 ready slots / MiB'),tr('槽进程 PSS 合计','Slot-process PSS total'),tr('每槽平均','Per-slot average'),tr('公共进程 PSS','Common-process PSS')]]+[[names[p]]+[f(memory[p]['summary'][k]) for k in ('slot_processes_pss_mib','slot_processes_average_pss_mib','common_processes_pss_mib')] for p in ('kuasar-fork','kuasar-mlink')],[180,110,100,120])
 text('5 次观察取中位数；槽进程为 64 个 VMM 及存在时的槽专属命名空间 holder。公共进程包含种子 VM、控制面和专属缓存/存储服务。此处是 64 槽下的归属统计，不冒充空池到满池的因果增量；PSS 不包含大多数内核内存和未映射页缓存。','Median of five observations. Slot processes include 64 VMMs and per-slot namespace holders where present. Common processes include the seed VM, controllers and dedicated cache/store services. This is attribution at 64 slots, not a causal empty-to-full increment; PSS excludes most kernel memory and unmapped page cache.','small')
 page('启动批次时间','Startup batch timestamps')
 text('时间为 UTC，各组统计保留各自的实际采集窗口。下表是每方全部语言和模式的首个、最后一个正式请求开始时间；不表示整个窗口连续施加相同负载。','Times are UTC. Groups retain their actual collection windows. The table spans the first and last measured request starts across each product’s languages/modes; it does not imply a continuous uniform workload.')
 rr=[[tr('对象','Product'),tr('最早请求开始 UTC','First request start UTC'),tr('最晚请求开始 UTC','Last request start UTC')]]
 for p in order:
  times=[load(path)['start_unix_ns']/1e9 for path in (R/'matrix').glob('*/'+p+'/*/[0-9][0-9].json')]
  rr.append([names[p]]+[datetime.fromtimestamp(t,timezone.utc).strftime('%Y-%m-%d %H:%M:%S') for t in (min(times),max(times))])
 table(rr,[110,200,200])
 page('证据、统计范围与复现','Evidence, scope and reproduction')
 text('启动：36 组 × 50 次正式样本，另有 36 次 warmup。运行中 fork：3 组 × 50 次，另有 3 次 warmup。资源：30 轮执行/CPU/IO，36 组双实例存储，24 组内存曲线/数组测试。持久化：6 组 × 50 次，另有 6 次 warmup。每一组在正文标清口径，不合并不同批次或不同负载分布。','Startup: 36 groups × 50 measured samples plus 36 warmups. Live fork: 3 × 50 plus 3 warmups. Resources: 30 execution/CPU/IO rounds, 36 two-instance storage cases and 24 memory-growth/array cases. Persistence: 6 × 50 plus 6 warmups. Different batches/workload distributions are not pooled.')
 text('源代码、原始 JSON、服务阶段日志和脚本哈希保存于 report-revision-113；报告从原始记录生成，拒绝缺失记录。串行与功能验证要求通过；突发测试的容量、请求和存活失败如实列出。默认预热参考不当作严格冷缓存结果。','Sources, raw JSON, service-stage logs and script hashes are stored under report-revision-113. The report is generated from complete raw records. Serial and functional validations must pass; burst capacity, request and retention failures are reported as observed. Default-warm references are not strict cold-cache results.')
 runtime=load(B/'runtime-binary-manifest.json');assert all(runtime['products'].get(p) for p in order)
 text('六方实际运行程序的 SHA-256 另存 runtime-binary-manifest.json；它记录本次专属部署的可执行文件，不依赖可能过期的版本标签。','SHA-256 hashes of all six dedicated deployments’ running executables are recorded in runtime-binary-manifest.json, independently of version labels.','small')
 provenance=load(B/'source-provenance-startup.json')
 table([[tr('代码库','Repository'),tr('基线提交','Base commit'),tr('测试时修改文件数','Changed files at test')]]+[[k,provenance[k]['head'][:16],len(provenance[k]['modified_files'])] for k in ('kuasar','accelerator','bench')],[140,220,150])
 text('表中提交是开发基线，不冒充未提交修改的版本。精确测试版本由同目录 source-provenance-startup.json 中的文件 SHA-256 和补丁确定；测试脚本另有哈希。','These are development base commits, not a claim that uncommitted modifications are represented by those commits. Exact tested versions are identified by per-file SHA-256 and patches in source-provenance-startup.json; benchmark scripts are hashed separately.','small')
 text('正式环境仅使用 113 的专属实例及公共测试互斥锁，没有修改他人的进程或 108 的分支。代码保留在 sandbox_fork_staging；未经批准不合入 sandbox_fork。','Formal runs use dedicated instances on 113 and a shared benchmark mutex. Other users’ processes and the 108 branch are untouched. Code stays on sandbox_fork_staging and is not merged into sandbox_fork without approval.')

def footer(canvas,doc):
 canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(NAVY);canvas.drawString(42,25,'113 · sandbox_fork_staging · report-revision-113');canvas.drawRightString(A4[0]-42,25,str(doc.page));canvas.restoreState()
SimpleDocTemplate(str(O/'sandbox-sixway-zh-en.pdf'),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=38,bottomMargin=40,title='Sandbox comparison / 六方沙箱综合报告',author='Benchmark study').build(story,onFirstPage=footer,onLaterPages=footer)
print(O/'sandbox-sixway-zh-en.pdf')
