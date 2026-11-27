"""Render audited 181 measurements only; no historical substitutions."""
from pathlib import Path
import json, re, statistics as S, math, hashlib, collections, datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line, PolyLine
from xml.sax.saxutils import escape

R=Path(__file__).parent; D=R/'report-data'; M=D/'measurements'; N=D/'native'
OUT=R/'sevenway-181-cn-en.pdf'
P=['fork2','kuasar-fork','kuasar-mlink','kuasar-off','kuasar-uffd','agentenv','cube']
LABEL=dict(zip(P,['Fork2','Fork (old)','memlink','Kuasar off','Kuasar UFFD','AgentENV','CubeSandbox']))
read=lambda p:json.loads(p.read_text())
def series(path):return [read(path/f'{i:02d}.json') for i in range(1,51)]
def med(a):return S.median(a) if a else None
def fmt(x):return '—' if x is None else f'{x:,.2f}'
def stat(a):
 a=sorted(a)
 return [med(a), a[math.ceil(.95*len(a))-1],a[math.ceil(.99*len(a))-1],max(a)] if a else [None]*4
def pct(x,y):return '—' if x is None or not y else f'{(x/y-1)*100:+.1f}%'
def startup(p,l):return series(M/'startup'/l/p)
def modes(p,l,m):
 path=(N/('snapshot-remote' if m=='remote' else 'snapshot-local')/l/m) if p=='fork2' else M/'snapshot-modes'/l/p/m
 return series(path) if (path/'50.json').exists() else []
def vals(a,k):return [v[k] for v in a if isinstance(v.get(k),(int,float))]

pdfmetrics.registerFont(TTFont('CN','/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'))
pdfmetrics.registerFont(TTFont('EN','/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'))
story=[];lang=False
def tr(c,e):return e if lang else c
def para(s,size=10):
 text=''.join(('<font name="CN">'+escape(t)+'</font>') if re.search(r'[\u2e80-\u9fff\uff00-\uffef]',t) else escape(t) for t in re.split(r'([\u2e80-\u9fff\uff00-\uffef]+)',str(s)))
 return Paragraph(text,ParagraphStyle('body',fontName='EN',fontSize=size,leading=size*1.4,spaceAfter=5,wordWrap='CJK'))
def page(c,e):
 if story:story.append(PageBreak())
 story.append(para(tr(c,e),20));story.append(Spacer(1,8))
def note(c,e):story.append(para(tr(c,e)))
def table(headers,rows,widths=None):
 data=[[para(x,8.4) for x in headers]]+[[para(x,8.1) for x in row]for row in rows]
 t=Table(data,colWidths=widths or [505/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8eff5')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#7795ad')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fb')]),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
 story.append(t);story.append(Spacer(1,9))
def bars(items,title):
 items=[(k,v)for k,v in items if v is not None];h=25*len(items)+35;d=Drawing(505,h);mx=max(v for _,v in items)or 1
 d.add(String(0,h-10,title,fontName='EN',fontSize=10))
 for i,(k,v) in enumerate(items):
  y=h-35-i*25;d.add(String(0,y,k,fontName='EN',fontSize=9));d.add(Rect(100,y-3,320*v/mx,13,fillColor=colors.HexColor('#24719b' if k=='Fork2' else '#8baabd'),strokeColor=None));d.add(String(425,y,fmt(v),fontName='EN',fontSize=9))
 story.append(d)
def lineplot(items,title,ylabel):
 d=Drawing(505,170);d.add(String(0,157,title,fontName='EN',fontSize=10));mx=max([max(v)for _,v in items if v]+[1]);palette=['#176ca4','#cc7043','#5a8b5c','#9863a7','#a38e34','#555555','#37a4a0']
 for i,(label,ys)in enumerate(items):
  if not ys:continue
  pts=[]
  for j,v in enumerate(ys):pts.extend([40+395*j/max(1,len(ys)-1),35+100*v/mx])
  if len(pts)>=4:d.add(PolyLine(pts,strokeColor=colors.HexColor(palette[i%7]),strokeWidth=.7))
  d.add(String(40+(i%4)*115,15-(i//4)*11,label,fontName='EN',fontSize=8,fillColor=colors.HexColor(palette[i%7])))
 d.add(Line(40,35,435,35));d.add(Line(40,35,40,135));d.add(String(0,135,fmt(mx),fontName='EN',fontSize=8));d.add(String(440,35,'index',fontName='EN',fontSize=8));d.add(String(40,142,ylabel,fontName='EN',fontSize=8));story.append(d)

# Audit independently from layout and preserve exact source hashes.
audit={'startup':[],'snapshot':[],'pool':[],'burst':[],'live':{},'limitations':[]}
for p in P:
 for l in ['python','node','ruby']:
  a=startup(p,l);assert len(a)==50 and all(x['success']and x['destroyed']for x in a)
  audit['startup'].append({'product':p,'language':l,'n':len(a),'digest':a[0]['image_digest']})
  for m in ['local_warm','local_cold','remote']:
   a=modes(p,l,m)
   if not a:continue
   assert len(a)==50 and all(x['success']and x['destroyed'] for x in a)
   if m!='remote':assert all(x['cache_preparation']['verified'] for x in a)
   audit['snapshot'].append({'product':p,'language':l,'mode':m,'n':len(a)})
 for gap in [0,10,25,50,100]:
  d=read(M/'burst'/p/str(gap)/'result.json');ok=[x for x in d['samples']if x.get('success')]
  assert len(d['samples'])==256 and len(ok)==d['successes'] and not d['owned_remaining']
  assert set(x['sandbox_id']for x in ok)<=set(d['isolation_verified_ids'])
  assert not d.get('server_remaining')
  audit['burst'].append({'product':p,'gap_ms':gap,'successes':len(ok),'failures':256-len(ok),'client_errors':dict(collections.Counter(x.get('error','').strip().splitlines()[-1] for x in d['samples']if not x.get('success')))})

pool={};slot={}
for p in P[:3]:
 path=N/'pool-preparation/current' if p=='fork2' else M/'pool-preparation'/p
 a=[read(path/f'{i:02d}.json')for i in range(1,21)];pool[p]=a;slot[p]=[];counts=[]
 for i,d in enumerate(a,1):
  if p=='fork2':z=[v['elapsed_ns']/1e6 for v in d['slots']]
  else:
   ev=[json.loads(l) for l in (path/f'{i:02d}-events.jsonl').read_text().splitlines() if l.strip()]
   z=[v['elapsed_ms'] for v in ev if v.get('event')=='prepared'] if p=='kuasar-fork' else [v['fields']['total_us']/1000 for v in ev if v.get('fields',{}).get('event')=='runtime_slot_prepare_execution']
  counts.append(len(z));slot[p]+=z
 audit['pool'].append({'product':p,'formal_rounds':20,'event_counts':counts})
 assert all(n>=64 for n in counts), (p,counts)

live=read(N/'live-fork-verified.json')[1:];oldlive=[read(M/'live-fork/kuasar-fork/python'/f'{i:02d}'/'result.json')for i in range(1,51)]
assert len(live)==50 and all(x['memory_inherited']and x['memory_writes_isolated']and x['survivor_exec']for x in live)
assert all(x['success']and x['independent_files']and x['independent_destroy']and not x['owned_remaining']for x in oldlive)
export=[];vm=[];phase_rows=[]
for i,row in enumerate(live,1):
 phases={}
 for line in (N/'live-fork-child-traces'/f'{i:02d}.jsonl').read_text().splitlines():
  d=json.loads(line);msg=d.get('MESSAGE','');m=re.search(r'phase=(\w+) elapsed_ms=([\d.]+)',msg)
  if m and 'sandbox='+row['parent_id'] in msg:phases[m[1]]={'ms':float(m[2]),'unix_ms':int(d['__REALTIME_TIMESTAMP'])/1000}
 assert 'resume_ack'in phases and 'pause_ack'in phases
 export.append(phases['resume_ack']['ms']-phases['pause_ack']['ms']);phase_rows.append(phases)
 s=(N/'live-fork-child-traces'/f'{i:02d}-child-vmm.log').read_text();m=re.search(r'VM_FORK pause_ms=([\d.]+)',s)
 assert m;vm.append(float(m[1]))
audit['live']={'fork2_n':50,'old_n':50,'fork2_export_pause_ms':stat(export),'fork2_vm_pause_ms':stat(vm),'old_probe_gap_ms':stat(vals(oldlive,'parent_progress_gap_ms'))}
refills={}
for gap in [0,10,25,50,100]:
 refills[gap]={}
 for p in ['fork2','kuasar-mlink']:
  base=M/'burst'/p/str(gap);d=read(base/'result.json');start=d['start_unix_ns'];end=d['cleanup_started_unix_ns']
  if p=='fork2':
   histories=[x for pool in read(base/'pool-history.json')['runner_pools']for x in pool.get('preparation_history',[])]
   events=sorted({x['run_id']:(x['ready_unix_ns'],x['elapsed_ns']/1e6)for x in histories if start<=x['started_unix_ns']<=x['ready_unix_ns']<=end}.values())
  else:
   events=[]
   for line in (base/'pool-events.jsonl').read_text().splitlines():
    x=json.loads(line);f=x.get('fields',{})
    if f.get('event')!='runtime_slot_prepare_execution':continue
    t=int(datetime.datetime.fromisoformat(x['timestamp'].replace('Z','+00:00')).timestamp()*1e9)
    if start<=t<=end:events.append((t,f['total_us']/1000))
   events.sort()
  refills[gap][p]=[v for _,v in events]
audit['refill_event_counts']={str(g):{p:len(v)for p,v in a.items()}for g,a in refills.items()}
audit['limitations']=['Fork2 image-based groups before corrected prepared_restore=false used cold fallback; do not describe them as generic image-pool performance. Burst groups were rerun on the corrected image pool.','PSS and cgroup memory are overlapping views, not additive.','RocksDB block-cache hits do not identify physical chunk memory-versus-disk source.','Legacy pool request-to-full includes service/template bootstrap, unlike single-slot event timing.','Old parent progress gaps include probe scheduling; not identical to hypervisor pause.','Failure attribution is bounded by retained server logs; uncorrelated 500 bodies remain unknown.']
audit['sources']=[{'path':str(p.relative_to(D)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in sorted(D.rglob('*.json'))]
(R/'report-audit.json').write_text(json.dumps(audit,indent=2))

for lang in [False,True]:
 page('181 七方测试：结果摘要','181 seven-product benchmark: summary')
 note('主机 10.193.241.181；全部采用本批次实测。新 Fork2、旧 Fork 与 memlink 相邻展示。差值 = (Fork2 / memlink − 1) × 100%；耗时和占用越低越好。','Host 10.193.241.181; fresh measurements only. Fork2, old Fork and memlink are adjacent. Delta = (Fork2 / memlink − 1) × 100%; lower latency and footprint are better.')
 metrics=[]
 for l in ['python','node']:
  metrics.append((l+' print / ms',[med(vals(startup(p,l),'interpreter_print_ms'))for p in P[:3]]))
 metrics.append((tr('64 槽准备 / s','64-slot preparation / s'),[med(vals(pool[p],'request_to_full_ms'))/1000 for p in P[:3]]))
 metrics.append((tr('保存 / ms','Save / ms'),[med(vals(read(M/'pause-restore'/(p+'.json'))['samples'][1:],'save_ms'))for p in P[:3]]))
 table([tr('指标（中位数）','Metric (median)'),*map(LABEL.get,P[:3]),tr('相对 memlink','vs memlink')],[[k,*map(fmt,v),pct(v[0],v[2])]for k,v in metrics])
 note('摘要同时覆盖执行、存储、内存、销毁及并发创建：这些项目口径不同，详细数值与百分比在对应正文页给出。256 请求必须同时看成功数与耗时，部分成功不能用来宣称整体更快。','Execution, storage, memory, destruction and concurrent creation are covered in the following sections with their own definitions and deltas. Interpret 256-request duration together with success counts; partial completion is not a faster full completion.')
 note('Fork2 无用户实例时产品总 PSS 为 278.87 MiB，memlink 为 1,774.59 MiB，低 84.3%；删除确认后的补满等待中位数为 10.67 ms 对 1,026.57 ms，低 99.0%。这些优势不能抵消本批次镜像创建及突发成功率的不足，执行性能仍需按具体工作负载判断。','Fork2 service-baseline PSS is 278.87 MiB versus memlink 1,774.59 MiB, 84.3% lower. Median refill wait after delete acknowledgement is 10.67 ms versus 1,026.57 ms, 99.0% lower. These strengths do not erase image-creation and burst-success weaknesses; execution performance remains workload-dependent.')
 table([tr('产品','Product'),tr('256 同发成功数','Simultaneous successes'),tr('全成功耗时 / s','All-success duration / s')],[[LABEL[p],str(read(M/'burst'/p/'0/result.json')['successes'])+'/256',fmt((read(M/'burst'/p/'0/result.json').get('all_256_print_ms') or 0)/1000) if read(M/'burst'/p/'0/result.json')['successes']==256 else '—']for p in P])
 note('重要：Fork2 镜像创建与资源批次存在恢复槽配置不匹配，走了冷启动后备路径；修正后的镜像池用于并发批次。下文明确区分，不将不同路径混称为通用池表现。','Important: Fork2 image creation/resource batches had restore-holder configuration incompatible with the image path and used cold fallback. Corrected image-pool configuration was used for burst batches. These paths are distinguished below.')

 page('测试定义与样本','Definitions and samples')
 note('Ready：客户端收到 guest shell 的随机标识，证明可以执行命令；不代表 Python 已启动。print：随后真正启动 Python、Node.js 或 Ruby，客户端收到解释器输出的随机标识。计时从创建请求前开始，包含 SDK/CLI、创建与解释器启动。没有语言专用预热。','Ready: client receives a random guest-shell marker, proving command execution; the interpreter has not necessarily started. print: client receives a different random marker emitted by a newly launched Python, Node.js or Ruby interpreter. Timing starts before create and includes SDK/CLI, creation and interpreter startup. No language-specific prewarming.')
 note('启动与暂停保存恢复：1 次 warmup + 50 次正式测量；资源/生命周期各 50 次；64 槽整池准备：1 次 warmup + 20 次正式测量、8 路准备及补槽。存储同/异内容各 3 次；内存按 0、1、10、25、50 实例采样。每个并发发送间隔执行 1 组 256 请求。warmup 不计入统计。','Startup and pause/save/restore: 1 warmup + 50 measured samples; resources/lifecycle: 50. Whole-pool preparation: 1 warmup + 20 measured rounds, 64 slots, 8 prepare/refill workers. Storage: 3 samples per same/different-content case. Memory: 0, 1, 10, 25, 50 instances. Each burst spacing: one 256-request group. Warmups are excluded.')
 note('P95/P99 使用最近秩法；最大值为本批次观测值。单轮并发不能估计跨批次分布。各产品顺序测试，不是同一瞬间的交错负载。所有非启动资源测试只使用 Python。','P95/P99 use nearest rank; maxima are observed values. One burst does not estimate a cross-run distribution. Products ran sequentially, not under identical simultaneous load. Non-startup resource tests use Python only.')
 for l in ['python','node','ruby']:
  note(l+': '+startup('fork2',l)[0]['image_digest'],l+': '+startup('fork2',l)[0]['image_digest'])

 for l in ['python','node','ruby']:
  page(l+'：从镜像创建到 Ready / print',l+': image creation to Ready / print')
  note('每项 50 次，单位 ms。Fork2 本批次为镜像冷启动后备路径；不能代替已修正通用池的单请求成绩。','50 samples, ms. Fork2 in this batch used image cold fallback; this is not a single-request measurement of the corrected generic image pool.')
  for k in ['native_ready_ms','interpreter_print_ms']:
   table([tr('Ready / ms','Ready / ms') if k=='native_ready_ms' else 'print / ms','Median','P95','P99','Max',tr('相对 memlink','vs memlink')],[[LABEL[p],*map(fmt,stat(vals(startup(p,l),k))),pct(med(vals(startup(p,l),k)),med(vals(startup('kuasar-mlink',l),k)))]for p in P])
  bars([(LABEL[p],med(vals(startup(p,l),'interpreter_print_ms')))for p in P],'Median request-to-print / ms')

 for mode in ['local_warm','local_cold','remote']:
  page('持久化快照启动：'+mode,'Persisted snapshot startup: '+mode)
  note({'local_warm':'已有本地原生快照；请求前使目标文件的数据页缓存驻留。','local_cold':'已有本地原生快照；请求前使目标数据页缓存为冷，不包含快照生成。','remote':'按 Manifest/chunk 路径恢复；使用实际配置的 RocksDB 缓存和存储端，不替换为 Redis，不强求来自内存。'}[mode],{'local_warm':'Existing native local snapshot; target data pages resident before request.','local_cold':'Existing native local snapshot; target data-page cache cold before request. Snapshot generation is excluded.','remote':'Manifest/chunk restoration using configured RocksDB cache and backing store, not Redis. An in-memory source is not assumed.'}[mode])
  for l in ['python','node','ruby']:
   table([l+' / ms','Ready med','print med','print P95','print P99','print max'],[[LABEL[p],fmt(med(vals(modes(p,l,mode),'native_ready_ms'))),*map(fmt,stat(vals(modes(p,l,mode),'interpreter_print_ms')))]for p in P if modes(p,l,mode)])
  note('memlink、AgentENV、CubeSandbox 没有本批次同口径的 local/remote 显式切换测量；不以普通创建成绩填充。','No equivalent explicit local/remote switching measurement was collected for memlink, AgentENV or CubeSandbox; ordinary creation results are not substituted.')
  bars([(LABEL[p],med(vals(modes(p,'python',mode),'interpreter_print_ms')))for p in P if modes(p,'python',mode)],'Python median request-to-print / ms')

 page('快照载体与请求前页缓存','Snapshot carriers and pre-request page cache')
 rows=[]
 for p in ['fork2','kuasar-fork','kuasar-off','kuasar-uffd']:
  for mode in ['local_warm','local_cold']:
   a=modes(p,'python',mode);cs=[x['cache_preparation'].get('after',x['cache_preparation'].get('files',[]))for x in a]
   rows.append([LABEL[p],mode,*[fmt(med([sum(v.get(k,0)for v in c)*scale for c in cs]))for k,scale in [('logical_bytes',1/2**20),('allocated_bytes',1/2**20),('resident_data_pages',4096/2**20)] ]])
 table([tr('产品','Product'),'Mode',tr('逻辑 MiB','Logical MiB'),tr('磁盘 MiB','Disk MiB'),tr('请求前页缓存 MiB','Pre-request cache MiB')],rows)
 note('逻辑大小是目标文件长度总和；磁盘占用按文件已分配块统计；页缓存驻留量是创建请求前 mincore 测得的目标文件驻留页总量。包含各路径实际依赖的快照、镜像及运行时文件；不同产品文件集合并不相同，不等于整机内存。','Logical size sums file lengths; disk footprint sums allocated file blocks; pre-request residency is measured with mincore on target files. The set includes actual snapshot, image and runtime dependencies and differs across products; it is not total host memory.')
 note('remote 的缓存命中计数与进程磁盘读取字节并不能严格推导 chunk 从物理内存/磁盘读取的百分比。本批次缺少统一逐 chunk 来源计数，故不伪造该百分比。','Cache hit counters and process disk-read bytes cannot strictly establish per-chunk physical memory/disk percentages. A uniform per-chunk source counter is unavailable in this batch, so no such percentage is fabricated.')

 page('执行、CPU/IO 与并发任务','Execution, CPU/IO and concurrent tasks')
 rr={p:series(M/'resources'/p)for p in P}
 metrics=[('short',lambda x:med(x['short_ms'])),('SHA-256',lambda x:x['cpu'][1]),('32 MiB write+fsync',lambda x:x['io'][1]),('2-client tasks/s',lambda x:x['throughput'])]
 for name,fn in metrics:
  table([name,'Median','Max',tr('相对 memlink','vs memlink')],[[LABEL[p],fmt(med([fn(x)for x in rr[p]])),fmt(max(fn(x)for x in rr[p])),pct(med([fn(x)for x in rr[p]]),med([fn(x)for x in rr['kuasar-mlink']]))]for p in P])
 note('短命令：已运行沙箱内执行短命令，统计客户端完成耗时。SHA-256：对 256 MiB 数据计算摘要，校验结果；CPU 列取 guest 计算时间。IO：写入 32 MiB 并 fsync，校验摘要。并发 2：两个客户端同时循环创建、执行并删除沙箱，共完成 8 项任务；吞吐=8/总秒数，越大越好，不是单个 CPU 的速度。','Short command: client completion time inside an existing sandbox. SHA-256: compute and verify a digest over 256 MiB; CPU uses guest computation time. IO: write 32 MiB and fsync with digest verification. Two-client throughput: two clients create, execute and delete eight tasks in total; throughput=8/total seconds, higher is better. It is not single-CPU speed.')

 page('持久化保存与恢复','Durable save and restore')
 a={p:[x for x in read(M/'pause-restore'/(p+'.json'))['samples']if not x['warmup']]for p in P}
 for k in ['save_ms','restore_api_ms','restore_print_ms']:
  title={'save_ms':tr('保存 / ms','Save / ms'),'restore_api_ms':tr('恢复 API / ms','Restore API / ms'),'restore_print_ms':tr('恢复至 print / ms','Restore to print / ms')}[k]
  table([title,'Median','P95','P99','Max'],[[LABEL[p],*map(fmt,stat(vals(a[p],k)))]for p in P])
 note('保存：发出暂停/持久化请求至 API 确认完成。恢复 API 返回不等于 guest 已能运行；恢复到 print 从恢复请求前计时，到新启动 Python 输出随机标识。保存前写入并同步文件，恢复后检查原进程继续、文件内容以及删除确认。','Save: pause/persist request to API acknowledgement. Restore API return does not prove guest readiness; restore-to-print starts before restore and ends on output from newly launched Python. Files are synced before save; process continuity, file content and deletion are verified after restore.')

 page('两沙箱存储增量','Storage growth for two sandboxes')
 for content in ['same','different']:
  rows=[]
  for p in P:
   a=[read(M/'storage'/p/f'{i}-{content}.json')for i in range(3)]
   v=[med([(x[k]['unique_extent_bytes']-x['baseline']['unique_extent_bytes'])/2**20 for x in a])for k in ['running','paused','settled']]
   rows.append([LABEL[p],*map(fmt,v)])
  table([content+' / MiB',tr('运行后新增','Running growth'),tr('保存后新增','Saved growth'),tr('删除后净增','Post-delete growth')],rows)
 note('基线为本产品两沙箱创建前；两沙箱各写入 32 MiB，同内容使用相同数据、异内容使用不同数据。用 FIEMAP 按文件系统去重物理区间统计本产品数据目录。保存后增量包括快照、元数据及缓存；删除后净增可包含保留制品，并非只统计用户文件。每种内容 3 次。','Baseline precedes creating two sandboxes. Each writes 32 MiB, using identical or different contents. FIEMAP de-duplicates physical extents per filesystem across product data directories. Saved growth includes snapshots, metadata and cache; post-delete growth can include retained artifacts, not just user files. Three samples per content type.')

 page('运行时内存：产品总 PSS','Runtime memory: product-wide PSS')
 mm={p:read(M/'memory'/(p+'.json'))for p in P}
 table([tr('产品 / MiB','Product / MiB'),'0','1','10','25','50'],[[LABEL[p],*[fmt(next(x['median']['pss_mib']for x in mm[p]['growth']if x['instances']==n))for n in [0,1,10,25,50]]]for p in P])
 note('统计本产品控制服务、代理及 VM 进程的 PSS：共享页按共享者比例分摊。0 实例表示没有用户沙箱时的服务基线；只有有预备池的产品才包含预备槽，不把 UFFD 等称为“空闲池”。不同实例数分别取稳定采样中位数。','PSS includes product controllers, proxies and VM processes; shared pages are proportionally attributed. Zero instances is the service baseline without user sandboxes. Prepared slots are included only for products with pools; UFFD is not described as having an idle pool. Each point uses the median of repeated samples.')
 table([tr('50 实例 / MiB','50 instances / MiB'),'PSS','cgroup total','cgroup file'],[[LABEL[p],*[fmt(next(x['median'].get(k)for x in mm[p]['growth']if x['instances']==50))for k in ['pss_mib','cgroup_current_mib','cgroup_file_mib']]]for p in P])
 note('cgroup total 包含该组计费的匿名页、文件页及内核开销；file 是其中的文件页。PSS 与 cgroup 是重叠视角，不能相加，也不能把文件页缓存当成免费内存。','cgroup total includes charged anonymous memory, file pages and kernel overhead; file is its file-page component. PSS and cgroup overlap and must not be added. File cache is not free memory.')

 page('内存写入与隔离','Memory writes and isolation')
 table([tr('PSS 新增 / MiB','Added PSS / MiB'),'zero','100','random'],[[LABEL[p],*[fmt(mm[p]['arrays'][k]['increment_pss_mib'])for k in ['zero','100','random']]]for p in P])
 note('50 个运行沙箱中分别保持 Python 进程，每个分配并触碰 20 MiB 数组；zero、100、random 是三种内容。新增 PSS 以已启动 Python、尚未分配数组的采样为基线，避免把解释器自身内存混入数组开销。','In 50 running sandboxes, keep Python processes alive, then allocate and touch 20 MiB per guest with zero, 100 or random contents. Added PSS is relative to Python already running before allocation, excluding interpreter overhead.')

 page('64 槽准备、删除与补满','64-slot preparation, deletion and refill')
 table([tr('产品','Product'),tr('整池中位 s','Pool med s'),tr('整池最大 s','Pool max s'),tr('单槽中位 ms','Slot med ms'),tr('单槽最大 ms','Slot max ms')],[[LABEL[p],fmt(med(vals(pool[p],'request_to_full_ms'))/1000),fmt(max(vals(pool[p],'request_to_full_ms'))/1000),fmt(med(slot[p])),fmt(max(slot[p]))]for p in P[:3]])
 note('每组 20 轮、64 槽、8 路准备/补槽。整池计时从脚本发出重建请求到 64 槽就绪，旧 Fork 与 memlink 包含服务重启及模板准备；单槽取服务内部事件，不将两者混称为同一开销。Fork2 保留的额外轮次不进入这张表。','20 rounds, 64 slots, 8 prepare/refill workers. Whole-pool timing starts at rebuild request and ends at 64 ready slots; old Fork and memlink include service restart/template preparation. Per-slot timing uses internal events and is a different scope. Extra retained Fork2 rounds are excluded.')
 table([tr('产品','Product'),tr('删除确认中位 ms','Delete ack med ms'),tr('补满等待中位 ms','Refill wait med ms'),tr('补满最大 ms','Refill wait max ms')],[[LABEL[p],fmt(med([x['delete_ack_ms']for x in series(M/'lifecycle'/p)])),fmt(med([x['pool_after']['elapsed_ms']for x in series(M/'lifecycle'/p)])) if p in P[:3]else '—',fmt(max(x['pool_after']['elapsed_ms']for x in series(M/'lifecycle'/p))) if p in P[:3]else '—']for p in P])
 note('删除确认：发出删除请求到 API 返回。补满等待：删除确认后继续等待池恢复到规定就绪容量；不等于后台单个补槽时长。无等价池的产品不填 0。','Delete acknowledgement: delete request to API return. Refill wait: additional wait after acknowledgement until the pool regains required ready capacity; not a single background refill duration. Products without equivalent pools show no value, not zero.')

 page('Python：从运行中父沙箱 fork','Python: fork from a running parent')
 table([tr('指标 / ms','Metric / ms'),'Median','P95','P99','Max'],[[tr('Fork2 子 Ready','Fork2 child Ready'),*map(fmt,stat(vals(live,'child_ready_ms')))], [tr('Fork2 子 print','Fork2 child print'),*map(fmt,stat(vals(live,'child_print_ms')))], [tr('旧 Fork 子 Ready','Old Fork child Ready'),*map(fmt,stat(vals(oldlive,'ready_ms')))], [tr('旧 Fork 子 print','Old Fork child print'),*map(fmt,stat(vals(oldlive,'print_ms')))], [tr('Fork2 导出暂停区间','Fork2 export paused interval'),*map(fmt,stat(export))], [tr('Fork2 VM fork 暂停','Fork2 VM fork pause'),*map(fmt,stat(vm))], [tr('旧 Fork 父进程最大步进间隔','Old Fork parent probe gap'),*map(fmt,stat(vals(oldlive,'parent_progress_gap_ms')))]])
 note('通过实际 HTTP 父沙箱 fork 接口发起，50 次。新 Fork2 导出暂停取 pause_ack 到 resume_ack；VM fork pause 是另一个底层区间，不能只用它代表整个操作。旧 Fork 使用 10 ms 进程探针的最大步进间隔，包含调度误差，不能直接视为精确 VM 暂停。','50 requests through the actual HTTP parent-fork endpoint. Fork2 export pause spans pause_ack to resume_ack. VM fork pause is a separate low-level interval, not the full operation. Old Fork uses a 10-ms process-probe gap, including scheduling error; it is not an exact VM-pause measurement.')
 idx=min(range(50),key=lambda i:abs(live[i]['child_print_ms']-med(vals(live,'child_print_ms'))));row=live[idx];ph=phase_rows[idx];t0=row['start_unix_ns']/1e6;end=row['child_print_ms'];d=Drawing(505,150)
 stages=[('API',0,row['fork_api_ms']),('Parent export pause',ph['pause_ack']['unix_ms']-t0,ph['resume_ack']['unix_ms']-t0),('Child ready -> print',row['child_ready_ms'],end)]
 for i,(name,a,b)in enumerate(stages):
  y=110-i*30;d.add(String(0,y,name,fontName='EN',fontSize=8));d.add(Rect(125+330*max(0,a)/end,y-3, max(1,330*(b-a)/end),12,fillColor=colors.HexColor('#4285a8'),strokeColor=None))
 for value in [row['child_ready_ms'],end]:
  x=125+330*value/end;d.add(Line(x,40,x,60,strokeColor=colors.HexColor('#183f5a'),strokeWidth=1))
 d.add(String(125,10,'0: request',fontName='EN',fontSize=8))
 for y,label,value in [(25,'Ready',row['child_ready_ms']),(10,'print',end)]:
  if not lang:d.add(String(300,y,'子',fontName='CN',fontSize=8))
  d.add(String(312 if not lang else 300,y,('' if not lang else 'child ')+label+' '+fmt(value)+' ms',fontName='EN',fontSize=8))
 story.append(d)
 note('时间图选取 print 最接近中位数的一次真实样本；横轴从请求为 0，重叠区间分行显示。不是把各阶段中位数拼成一次请求。父子内存/文件独立和任意先后删除已验证。','Timeline uses one real sample nearest median print, starting at request time zero. Overlapping intervals use separate lanes; phase medians are not spliced into a fictitious request. Parent/child memory and file isolation and both deletion orders were verified.')

 for gap in [0,10,25,50,100]:
  page('256 请求：'+str(gap)+' ms 发送间隔','256 requests: '+str(gap)+' ms spacing')
  rows=[];plots=[]
  for p in P:
   d=read(M/'burst'/p/str(gap)/'result.json');ok=d['successes'];rows.append([LABEL[p],str(ok)+'/256',fmt(d['all_requests_finished_ms']/1000),fmt(d['all_256_print_ms']/1000) if ok==256 else '—']);plots.append((LABEL[p],d['completion_gaps_ms']))
  table([tr('产品','Product'),tr('print 成功','print successes'),tr('请求全部结束 s','All requests ended s'),tr('256 全成功 s','All 256 print s')],rows)
  lineplot(plots,'Intervals between successive successful prints','ms')
  note('全部成功实例保留到所有请求结束后统一销毁。横坐标是成功完成序号，纵坐标是相邻成功完成间隔；首点为首个 print 距离请求起点。失败请求没有 print，不能伪装成完成点。全部请求结束包含失败，不等于 256 个成功。','All successful instances are retained until requests finish, then destroyed together. X is successful completion index; Y is the interval since the preceding success, with the first point measured from request start. Failures produce no completion point. All requests ended includes failures; it does not imply 256 successes.')

 page('突发期间的补槽耗时','Refill durations during bursts')
 for gap in [0,10,25,50,100]:
  table([str(gap)+' ms gap',tr('完成事件数','Completed events'),'Median ms','Max ms'],[[LABEL[p],str(len(v)),fmt(med(v)),fmt(max(v))if v else '—']for p,v in refills[gap].items()])
 note('仅统计请求开始至统一销毁开始之前完成的补槽事件；按完成先后排序。Fork2 采用准备历史环形缓冲区，可能只保留末尾事件，事件数不代表全部补槽数；memlink 使用事件日志。不同服务的事件边界不完全相同，不将单槽时长相加当作整批耗时。','Only refill events completed after request start and before uniform cleanup are included, ordered by completion. Fork2 history is a ring buffer and may retain only the tail; its count is not the total refill count. memlink uses event logs. Event boundaries differ and per-slot durations must not be summed as batch duration.')
 page('补槽时间图：完成序号与耗时','Refill charts: completion index and duration')
 for gap in [0,10,25]:lineplot([(LABEL[p],v)for p,v in refills[gap].items()],str(gap)+' ms request spacing','refill ms')
 page('补槽时间图：较稀疏请求','Refill charts: paced requests')
 for gap in [50,100]:lineplot([(LABEL[p],v)for p,v in refills[gap].items()],str(gap)+' ms request spacing','refill ms')

 page('并发失败的实际原因','Observed concurrent-creation failures')
 table([tr('产品','Product'),tr('本批次证据与解释','Evidence and interpretation')],[[LABEL['fork2'],tr('服务端出现 context deadline exceeded；客户端多为 HTTP 500，少量 503。准备槽接入提交存在串行等待；不能据此称为容量 64 上限。','Server context deadline exceeded; mostly HTTP 500 and some 503. Prepared admission commits show serialized waiting; this is not proof of a 64-instance capacity limit.')],[LABEL['kuasar-fork'],tr('客户端 503：No prepared template slot available。补槽不能及时满足本轮突发。','Client 503: No prepared template slot available. Refill did not keep up with this burst.')],[LABEL['kuasar-off']+' / '+LABEL['kuasar-uffd'],tr('服务端 artifact_prepare 超时，并有 SQLite 锁冲突；已返回 ID 的实例后台失败导致 sandbox not found。部分 500 响应格式不符合 SDK，表现为 KeyError(code)，不能只从该错误推断更细根因。','Server artifact_prepare deadlines and SQLite lock contention. IDs may be returned before background launch fails, yielding sandbox not found. Some malformed 500 responses become SDK KeyError(code); finer attribution cannot be inferred from that alone.')],[LABEL['cube'],tr('同时发送组的 103 个失败为 429 限流；四种间隔组全部成功。','103 simultaneous-group failures were 429 rate limiting; all paced groups succeeded.')],[LABEL['kuasar-mlink'],tr('正式有效组均 256 成功。客户端 FD 上限造成的无效测量另存证据，修复压测进程后补跑，不计入正式结果。','All valid groups succeeded 256/256. A client-FD-limited invalid run was archived and replaced after correcting the load-generator limit.')],[LABEL['agentenv'],tr('五组全部 256 成功。','All five groups succeeded 256/256.')]])
 note('未知原因保留为未知，不把所有失败归因为慢。运行容量、网络容量、预备池大小与等待队列分别配置；报告中的结果描述该部署实际表现。','Unresolved causes remain unresolved; failures are not all attributed to slowness. Runtime capacity, network capacity, prepared-pool size and queue capacity are separate settings. Results describe this deployment.')
 page('失败请求与服务端日志关联','Failed requests correlated with server logs')
 attribution=read(R/'server-failure-attribution.json')
 table([tr('产品','Product'),'Gap ms','artifact_prepare','network_commit','runtime',tr('未能细分','Unresolved')],[[LABEL[x['product']],str(x['gap_ms']),str(x['correlated_failure_stages'].get('artifact_prepare',0)),str(x['correlated_failure_stages'].get('network_commit',0)),str(x['correlated_failure_stages'].get('runtime',0)),str(x['correlated_failure_stages'].get('unresolved_or_no_returned_id',0))]for x in attribution])
 note('按返回的沙箱 ID 关联本批次日志中的终止失败阶段。artifact_prepare 表示制品/运行器准备阶段，network_commit 表示网络提交阶段，runtime 表示运行时阶段。没有返回 ID 或没有可关联终止日志的失败单列为“未能细分”，不强行归类。此表记录失败发生阶段，不声称已证明所有超时的底层原因。','Correlates returned sandbox IDs with terminal failure stages in retained logs. artifact_prepare is artifact/runner preparation; network_commit is network commit; runtime is the runtime phase. Requests without a returned ID or matching terminal log remain unresolved. These are failure stages, not proof of every underlying timeout cause.')

def footer(c,doc):
 c.setFont('EN',8);c.setFillColor(colors.HexColor('#526674'));c.drawString(45,25,'181 | Fresh seven-product benchmark | 2026-11-25–26');c.drawRightString(550,25,str(doc.page))
SimpleDocTemplate(str(OUT),pagesize=(595,842),rightMargin=45,leftMargin=45,topMargin=40,bottomMargin=42,title='181 Seven-product benchmark | Chinese and English',author='Benchmark analysis').build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
