"""Chinese startup report with measured overlapping timelines (ReportLab)."""
from pathlib import Path
import html
import json
import math
import statistics
import sys
from reportlab.graphics.shapes import Drawing, Rect, Line, String
from reportlab.graphics import renderSVG
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

B = Path(sys.argv[1])
R = B/'results/matrix'
OUT = B/'report'
OUT.mkdir(exist_ok=True)
live = json.loads((B/'results/live-formal/analyzed.json').read_text())
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
FONT = 'STSong-Light'
NAVY = colors.HexColor('#153550')
styles = {name: ParagraphStyle(name, fontName=FONT, fontSize=size, leading=lead,
    textColor=NAVY, spaceAfter=8, wordWrap='CJK') for name,size,lead in
    [('title',20,28),('heading',13,20),('body',10,16),('small',8,12)]}
story = []
def text(s, style='body'):
    story.append(Paragraph(s, styles[style]))
def page():
    story.append(PageBreak())
def table(rows, widths):
    t = Table([[Paragraph(html.escape(str(c)),styles['small']) for c in row] for row in rows],
              colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e5eef5')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f4f7fa')]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),
        ('BOTTOMPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,0),.5,NAVY)]))
    story.extend([t,Spacer(1,10)])
def stats(values):
    values = sorted(values)
    assert len(values) == 10
    return dict(median=statistics.median(values),p95=values[math.ceil(.95*len(values))-1],
                p99=values[math.ceil(.99*len(values))-1],max=values[-1])
def rows(product,language,mode):
    directory = R/language/product/mode
    result = [json.loads((directory/f'{i:02d}.json').read_text()) for i in range(1,11)]
    assert all(r['success'] and r['destroyed'] for r in result)
    return result
def fmt(x):return f'{x:.2f}'
def pair(group,key):
    s=stats([r[key] for r in group]);return fmt(s['median'])+' / '+fmt(s['max'])
names={'kuasar-fork':'fork','kuasar-mlink':'mlink','agentenv':'AgentENV','cube':'CubeSandbox',
       'kuasar-off':'Kuasar off','kuasar-uffd':'Kuasar UFFD'}
languages={'python':'Python','node':'Node.js','ruby':'Ruby'}
order=['kuasar-fork','kuasar-mlink','agentenv','cube','kuasar-off','kuasar-uffd']

text('113 六方沙箱综合报告','title')
text('本轮启动 / 三种语言 / 每组 1 次 warmup + 10 次串行测量','heading')
text('本轮新增启动模式与运行中 fork；执行、CPU/IO、内存、存储和持久化生命周期沿用已验证的完整资源批次 A，均在正文标明来源与限制，不混入本轮统计。','small')
text('本报告区分模板创建与“从正在运行的父沙箱派生”。所有计时起点均为客户端发出请求之前；启动实际解释器执行随机 print，不用 shell 输出冒充语言启动。固定镜像 digest，2 vCPU / 2 GiB；fork 与 mlink 的通用 VM 池容量均为 2。')
table([['指标','定义'],
 ['API','创建或 HTTP fork 请求发出，到客户端收到响应。响应不等于 guest 已可执行。'],
 ['Ready','同一 exec 流中，客户端收到 shell 输出的随机 NATIVE 标识。它证明命令已可执行，但尚未证明语言解释器启动完成。'],
 ['print','客户端收到解释器输出的随机 READY 标识，包含解释器启动与输出传输。'],
 ['父暂停','VMM pause_begin 到父 VM resume_done；另记录全部 vCPU 停止后的窗口。'],
 ['子恢复','请求发出到子 VM resume_done；它早于客户端 Ready，不与 Ready 混用。']],[75,435])
text('模式定义与适用范围','heading')
table([['模式','实际条件'],
 ['local warm','已有本地原生快照，目标载体数据缓存已热；以 mincore 验证每页驻留。'],
 ['local cold','相同原生快照，每次请求前对指定文件 fsync + fadvise(DONTNEED)，以 mincore 验证零驻留。没有全机 drop_caches。'],
 ['remote / 内存','走 Manifest/chunk 恢复及解密校验；chunk 从独立内存缓存取得。remote 指载体/恢复路径，并不表示本轮测了跨地域网络 RTT。'],
 ['运行中 fork','HTTP POST /sandboxes/{parent_id}/fork，派生当前父沙箱状态，不领取预备子沙箱替代父状态。']],[92,418])
text('VM 池状态与数据缓存冷暖分别记录。准备、缓存预填充、销毁与补槽均不藏进启动指标，成本在正文单列。10 个样本的 nearest-rank P95/P99 均等于最大值，不据此声称稳定的生产长尾分布。','small')

page();text('覆盖范围与可比性','title')
table([['对象','本地原生冷/热','Manifest/chunk 内存','运行中 fork'],
 ['fork','实测','当前路径未接入','实测'],
 ['mlink','默认预热池参考；未建立严格冷缓存配置','未建立等价配置','本轮未测'],
 ['AgentENV','默认预热参考；未建立严格冷缓存配置','未建立等价配置','本轮未测'],
 ['CubeSandbox','默认预热参考；未建立严格冷缓存配置','未建立等价配置','本轮未测'],
 ['Kuasar off','实测','实测','本轮未测'],
 ['Kuasar UFFD','实测','实测','本轮未测']],[78,180,150,102])
text('“未建立等价配置”不是断言产品不支持该能力。mlink、AgentENV、CubeSandbox 的池、块设备和私有缓存不能用简单清除宿主页缓存模拟，因此不填伪造的 local cold / remote 数字。六方参考表保留各自默认预热路径，严格模式对比仅列已经验证载体与缓存状态的产品。')
text('Kuasar off/UFFD 的本地组由同一 Manifest 快照导出；不仅转换内存与可写层，也物化原来的 immutable image 引用，保留内容等价验证。最终 resolved config 不含 Manifest 引用。最初混合载体试跑已单独归档，不计入正式原生组。')
text('没有语言专用预热或预先运行解释器。fork 现有模板包含通用的目录/文件缓存准备；这一实现差异仍然存在，成本单列，不宣称六方 guest 内部缓存完全相同。cold 操作只改变宿主目标载体缓存，不清除快照里原本保存的 guest 页缓存。')
text('固定镜像与启动命令','heading')
config=json.loads((B/'config-public.json').read_text())
for lang,label in languages.items():
    text(label+'：'+config['_languages'][lang]['digest'],'small')
text('Python：/usr/local/bin/python3 -c「import sys; print(sys.argv[1], flush=True)」<br/>Node.js：/usr/local/bin/node -e「process.stdout.write(process.argv[1] + "\\n")」<br/>Ruby：/usr/local/bin/ruby -e「STDOUT.sync = true; puts ARGV.fetch(0)」','small')
text('三者均通过 /bin/bash -l -c 执行；先输出随机 NATIVE 标识，再 exec 解释器输出另一个随机 READY 标识。每次使用新标识，计时包含 SDK/CLI 开销。','small')
identity=json.loads((B/'image-verification.json').read_text())
assert identity['all_18_verified'] and identity['same_interpreter_hash_within_each_language']
text('计时结束后，另用 18 个可销毁沙箱核对：每种语言的六方解释器版本与二进制 SHA-256 一致；均为 2 vCPU / 约 2 GiB；检查前没有已运行的 Python/Node/Ruby 进程。该校验不回写模板，也不计入 10 次样本。','small')

page();text('六方参考：默认预热路径','title')
text('单位 ms；每格为“中位数 / 最大值”。fork/mlink 相邻；其余路径不强行标作原生 local warm。Kuasar off/UFFD 参考使用本轮 remote 内存组。')
reference={}
for lang,label in languages.items():
    text(label,'heading')
    data=[['对象 / 路径','请求→Ready','请求→print','fork print 相对该方']]
    fork_rows=rows('kuasar-fork',lang,'local_warm')
    f=stats([r['print_ms'] for r in fork_rows])['median']
    for product in order:
        mode='local_warm' if product=='kuasar-fork' else 'remote' if product in ('kuasar-off','kuasar-uffd') else 'product_default_warm'
        group=rows(product,lang,mode)
        m=stats([r['print_ms'] for r in group])['median']
        reference[(product,lang)]=group
        data.append([names[product],pair(group,'ready_ms'),pair(group,'print_ms'),
                     '—' if product=='kuasar-fork' else f'{(f/m-1)*100:+.1f}%'])
    table(data,[150,120,120,120])

page();text('本地原生快照：冷与热','title')
text('每组 10 次；每次 cold 样本（包括 warmup 后的正式样本）重新驱逐并验证。各格为中位数 / 最大值，单位 ms。')
data=[['对象 / 语言','warm Ready','cold Ready','warm print','cold print']]
cache_summary=[]
for product in ['kuasar-fork','kuasar-off','kuasar-uffd']:
    for lang,label in languages.items():
        warm=rows(product,lang,'local_warm');cold=rows(product,lang,'local_cold')
        assert all(r['cache_preparation']['verified'] for r in warm+cold)
        assert all(r['cache_preparation']['resident_pages']==0 for r in cold)
        data.append([names[product]+' / '+label,pair(warm,'ready_ms'),pair(cold,'ready_ms'),pair(warm,'print_ms'),pair(cold,'print_ms')])
        cache_summary.append([names[product]+' / '+label,
            fmt(statistics.median(r['cache_preparation']['preparation_ms'] for r in warm)),
            fmt(statistics.median(r['cache_preparation']['preparation_ms'] for r in cold)),
            fmt(warm[0]['cache_preparation']['pages']*4096/1024**3)])
table(data,[125,96,96,96,97])
text('冷暖条件建立成本（计时外，明确单列）','heading')
table([['对象 / 语言','热缓存填充 ms','冷缓存驱逐 ms','目标逻辑 GiB']]+cache_summary,[180,120,120,90])
text('缓存条件作用于发布目录（包含中间载体版本）；原生载体可能包含稀疏文件，逻辑大小不等于物理占用。此处为严格确认全部目标页热而顺序读取文件，包含空洞的逻辑读取开销。这是基准条件建立成本，不能解释成产品每次补槽都需要的成本。','small')

page();text('remote：chunk 实际来自哪里','title')
text('本轮使用独立 Redis 内存缓存（Unix socket），关闭缓存自身 RDB/AOF；权威持久化 Store 仍保留。Manifest、chunk 编码、解密和完整性验证路径未绕过。先预填充，再正式计时。缓存关闭持久化只针对可丢弃副本，不是删除快照持久化屏障。')
data=[['对象 / 语言','Ready 中位 / 最大','print 中位 / 最大','回源 / 磁盘读取']]
for product in ['kuasar-off','kuasar-uffd']:
    for lang,label in languages.items():
        group=rows(product,lang,'remote')
        evidence=[r['remote_cache'] for r in group]
        assert all(e['memory_served_evidence'] for e in evidence)
        data.append([names[product]+' / '+label,pair(group,'ready_ms'),pair(group,'print_ms'),
                     str(sum(e['origin_fetches'] for e in evidence))+' 次 / '+str(sum(e['cache_daemon_disk_read_bytes'] for e in evidence))+' B'])
table(data,[145,120,130,115])
text('验证依据：缓存服务进程及内存后端磁盘 read_bytes 增量、origin fetch 计数、内存缓存命中计数。每个正式请求均要求零回源、零磁盘读取。配置与原始计数保存在样本 JSON 中。')
text('原有 RocksDB 路径作为诊断批次保留：即使 origin 为零，大 chunk 的 BlobDB 文件仍产生约 20 MB/次的读取，不能把“未回源”误称为“纯内存命中”。正文采用验证通过的内存组；诊断批次不混入统计。')
if (B/'memory-preparation.json').exists():
    prep=json.loads((B/'memory-preparation.json').read_text())
    text('内存缓存准备成本（独立空缓存准备批次）','heading')
    text('缓存进程及 Redis 均从新实例启动；权威 Store 已存在且未强制冷却。准备测量与启动正式样本为独立批次，配置和来源相同。','small')
    table([['项目','数值']]+[[k,str(v)] for k,v in prep.items() if isinstance(v,(str,int,float))],[200,310])

page();text('模板载体与池准备成本','title')
text('本轮复用已经按固定 digest 构建的三语言模板，不重新下载镜像或执行语言预热。下面为本轮新增的载体转换、诊断部署和池策略准备，均不计入请求→Ready/print。不能把这些数值当作从零拉取镜像、构建模板的总成本。')
data=[['对象 / 语言','S/E 原生发布 ms','不可变镜像物化及验证 ms']]
for product in ['kuasar-off','kuasar-uffd']:
    for row in json.loads((B/(product+'-native.json')).read_text()):
        data.append([names[product]+' / '+languages[row['language']],fmt(row['publish_ms']),
                     fmt(row['image_materialization_ms'])])
table(data,[170,145,195])
deployment=json.loads((B/'trace-deployment.json').read_text())
text('fork 启用诊断后的部署与池重建总墙钟：'+fmt(deployment['elapsed_ms'])+' ms。包括清理旧空闲槽位、发布诊断二进制、启动 seed、准备通用资源和等待池就绪；没有把这笔成本挪进计时外而不披露。')
data=[['mlink 模板','本轮策略切换/预热等待 ms','预备槽位']]
for lang,label in languages.items():
    p=json.loads((R/'preparation'/lang/'policy-preparation.json').read_text())
    data.append([label,fmt(p['elapsed_ms']),p['vm_pool_capacity']])
table(data,[170,240,100])
text('mlink 按语言切换已有模板的存储预热策略，通用 VM 池仍为 2；fork 也复用一个通用 VM 池。切换等待不是完整模板构建耗时。AgentENV/Cube 本轮复用已有部署，其原始构建成本未重新计时，不能填为零。')

page();text('从运行中的父沙箱直接 fork','title')
text('当前 E2B SDK 2.25.1 没有 Sandbox.fork()。实际请求是 POST /sandboxes/{parent_id}/fork，返回子 ID 后用 Sandbox.connect() 连接，再执行命令。HTTP 请求、连接和首次解释器启动全部在端到端计时内。')
data=[['语言 / 指标','中位数 ms','P95 ms','P99 ms','最大 ms']]
for lang,label in languages.items():
    for key,title in [('parent_pause_ms','父暂停'),('child_resume_ms','请求→子恢复'),('ready_ms','请求→子 Ready'),('print_ms','请求→子 print')]:
        s=live[lang]['metrics'][key]
        data.append([label+' / '+title]+[fmt(s[k]) for k in ['median','p95','p99','max']])
table(data,[190,80,80,80,80])
text('30/30 正式样本通过：父进程计数在内存中持续递增；子分支继承同一 PID 和计数状态并继续运行；父子文件随后分别写为不同内容；交替先删父、先删子，存活分支仍能执行语言命令并继续计数；每个样本最后清理两者。')
text('开始计时前父沙箱已运行且网络就绪，等待成本计入父沙箱准备项。父 guest 的 10 ms 计数探针仅用于验证进程延续，不作为精确暂停时钟。guest 的虚拟时钟补偿与调度会影响观察间隙；父暂停使用同宿主 CLOCK_MONOTONIC 的 VMM 事件。模板准备、创建运行中父沙箱及上传探针在计时外，逐样本记录。')
table([['语言','建立运行中父沙箱：中位 / 最大 ms','父 vCPU 停止窗口中位 ms']]+[
    [languages[l],fmt(live[l]['metrics']['preparation_ms']['median'])+' / '+fmt(live[l]['metrics']['preparation_ms']['max']),
     fmt(live[l]['metrics']['parent_all_vcpus_stopped_ms']['median'])] for l in languages],[90,280,140])

def timeline(row):
    spans=row['spans']
    lane_order=['客户端','父 VM 暂停窗口','父 VM','子 VM','父 API','子 API','控制面','服务端持久化','异步网络']
    spans=sorted(spans,key=lambda s:(lane_order.index(s['lane']),s['start_ms']))
    left=207; right=470; step=17; height=40+step*len(spans)
    maximum=max(s['end_ms'] for s in spans)
    limit=math.ceil(maximum/20)*20
    d=Drawing(510,height)
    for value in range(0,limit+1,20):
        x=left+(right-left)*value/limit
        d.add(Line(x,25,x,height-8,strokeColor=colors.HexColor('#dbe3eb'),strokeWidth=.4))
        d.add(String(x,9,str(value),fontName=FONT,fontSize=8,textAnchor='middle'))
    palette=['#2c6f9e','#b54848','#d99c36','#4d9a77','#8271ad','#8271ad','#3c8294','#95744c','#5872ad']
    for i,s in enumerate(spans):
        y=height-25-i*step
        col=colors.HexColor(palette[lane_order.index(s['lane'])])
        d.add(String(0,y+1,s['lane']+' / '+s['label'],fontName=FONT,fontSize=7.2,fillColor=NAVY))
        x=left+(right-left)*s['start_ms']/limit
        width=max(.6,(right-left)*(s['end_ms']-s['start_ms'])/limit)
        d.add(Rect(x,y,width,9,fillColor=col,strokeColor=None))
        d.add(String(508,y+1,fmt(s['duration_ms']),fontName=FONT,fontSize=7.3,textAnchor='end'))
    d.add(String(left,0,'请求发出 = 0；横轴 ms；右列为阶段耗时 ms',fontName=FONT,fontSize=8))
    return d

for lang,label in languages.items():
    for choice,title in [('representative','接近端到端中位数的真实样本'),('maximum','最大端到端耗时样本')]:
        row=live[lang][choice]
        page();text(label+' 运行中 fork 时间图','title')
        text(title+' / 第 '+str(row['index'])+' 次','heading')
        text('父暂停 '+fmt(row['parent_pause_ms'])+' ms；子 Ready '+fmt(row['ready_ms'])+' ms；子 print '+fmt(row['print_ms'])+' ms。')
        drawing=timeline(row)
        story.append(drawing)
        story.append(Spacer(1,12))
        renderSVG.drawToFile(drawing,str(OUT/(lang+'-'+choice+'.svg')))
        text('每条横条来自该次请求的真实起止事件；纵向分行保留重叠关系，不把各阶段中位数拼成一条虚构时间线。父暂停窗口、父子恢复与 API 绑定互有嵌套，不能直接求和。','small')
        text('*“恢复后控制处理”是两分支 resume 完成到 sandbox-fork 管理 RPC 返回之间的实测区间，包含连接/身份处理及宿主收尾；尚无精确起止的子阶段未单独画成精确条。持久化含异步网络状态提交；图中显示的网络完成 RPC 不代表已单独测出完整 CNI 调用区间。','small')

resource=json.loads((B/'resource-suite.json').read_text())
assert resource['not_remeasured_in_startup_modes_batch']
old=resource['products']
def number(value):return '未测得' if value is None else fmt(value)
page();text('执行性能与 CPU/IO','title')
text('完整资源批次 A：sixway-aligned-20261117；Python 模板；每方 5 轮；fork/mlink 池 64。本轮未重跑此套件，不代表当前带诊断部署的资源性能。','heading')
table([['对象','短 exec ms','CPU ms','32 MiB IO ms','并发 2 任务/s']]+[
    [names[n]]+[number(old[n][key]) for key in ['short_ms','cpu_ms','io_ms','throughput']] for n in order],
    [130,90,90,100,100])
text('短 exec：每轮 8 次 true 的客户端完成时间，轮内中位数后再取 5 轮中位数。CPU：SHA-256 处理 256 MiB 的 guest 墙钟。IO：确定性生成、哈希、写入与 fsync。吞吐包含创建、Python print、计算校验和销毁，是容量 64 的短突发，不是持续补槽稳态吞吐。')
text('批次 A 的 fork 相对 mlink：'+ '；'.join(
    label+' '+f'{(old["kuasar-fork"][key]/old["kuasar-mlink"][key]-1)*100:+.1f}%'
    for key,label in [('short_ms','短 exec'),('cpu_ms','CPU 耗时'),('throughput','吞吐')]
    if old['kuasar-mlink'][key]>0)+'。时间越低越好，吞吐越高越好。')
text('<b>该批次的语义限制：</b>fork 业务文件当时使用 guest RAM overlay，fsync 不代表宿主断电后的持久化；因此 IO 不与持久化块盘排名，也不计算 IO 优劣百分比。这不等于本轮新版 fork 的文件系统配置；不能把旧批次结果改名为新版持久化块盘结果。')

page();text('内存：50 实例与数组负载','title')
text('完整资源批次 A / Python / 资源池 64 / 本轮未重测','heading')
table([['对象','0 实例 PSS MiB','50 实例 PSS MiB','增量 MiB/实例']]+[
    [names[n],fmt(old[n]['memory']['levels']['0']),fmt(old[n]['memory']['levels']['50']),
     fmt(old[n]['memory']['increment_per_instance'])] for n in order],[130,130,130,120])
text('PSS 包含产品服务、seed/预备资源及相关进程。观测点采 3 次取中位数；每实例增量为 (50 实例−0 实例)/50。PSS 不包含未映射的宿主页缓存及全部内核/设备开销，不能代表整机总内存。')
table([['对象','1 实例','10 实例','25 实例','50 实例']]+[
    [names[n]]+[fmt(old[n]['memory']['levels'][str(k)]) for k in [1,10,25,50]] for n in order],
    [130,95,95,95,95])
text('50 个进程的 20 MiB bytearray：PSS 增量 MiB','heading')
table([['对象','零值','值 100','随机值']]+[
    [names[n]]+[fmt(old[n]['memory']['arrays'][k]) for k in ['default','100','random']] for n in order],
    [180,110,110,110])
text('数组增量相对同组“Python 已启动、但未分配数组”的基线；仅在 50 个任务共同持有内存的窗口采样，至少 3 个有效观测，不是相对空 VM 的增量。')

page();text('存储：双沙箱独立写入与共享','title')
text('完整资源批次 A / 每沙箱写 32 MiB / 每种内容 3 轮 / 本轮未重测','heading')
for key,label in [('same','相同内容'),('different','不同内容')]:
    text(label+'：中位数，MiB','heading')
    table([['对象','运行态物理增量','暂停态物理增量','运行态 PSS 增量']]+[
        [names[n],number(old[n]['storage'][key]['live2']['extent_mib']),
         number(old[n]['storage'][key]['paused2']['extent_mib']),
         number(old[n]['storage'][key]['live2']['pss_mib'])] for n in order],
        [150,120,120,120])
text('物理占用取 FIEMAP extent 并集，避免重复计数 reflink 共享 extent；每轮扣除自己的 before 基线。不同文件系统分别求并集后相加。运行态物理增量不等于逻辑文件大小，也不等于单个容器的独占占用。')
text('所有写入校验确定性摘要；支持暂停/恢复的对象恢复后再次校验。“未测得”不等于零。此批 fork 使用 RAM overlay，不能拿低磁盘增量宣称持久化存储优势，因此不列存储百分比排名。')

page();text('持久化生命周期与资源准备','title')
text('完整资源批次 A / 每方 5 轮 / 本轮未重测','heading')
table([['对象','创建→print 中位','最大 ms','暂停 ms','恢复→print ms']]+[
    [names[n]]+[number(old[n][k]) for k in ['print_ms','print_max_ms','pause_ms','resume_ms']] for n in order],
    [130,105,85,90,100])
text('旧套件原始字段 ready_ms 的终点实际是 Python print，本表已正确标为 print；不能与本轮 native Ready 混用。暂停/恢复使用产品正常持久化接口，恢复后启动 Python 并校验文件摘要。')
text('批次 A 未测得 fork 的持久化暂停/恢复数值，保留为“未测得”，不据此断言当前新版不支持恢复。本轮新增的是运行中父沙箱 fork 的进程延续、文件隔离和独立销毁验证，并非重新测量持久化恢复或断电恢复。')
table([['资源测试准备项目','批次 A 耗时 ms'],
    ['2 槽位扩为 64 槽位的服务重置',fmt(resource['preparation']['service_reset_ms'])],
    ['随后等待池就绪与预热',fmt(resource['readiness']['elapsed_ms'])]],[340,170])
text('A 的审计记录确认执行/CPU/IO 30 组、并发任务 240 请求、存储 36 组、内存 24 组通过，并清理测试对象。本轮重新读取与校验这 93 份输入文件，保存输入 SHA-256；没有将它们伪装成重新执行后的结果。')
text('资源结果来源：/home/hong/src/research/sixway-aligned-20261117/results。归纳与输入校验保存在 resource-suite.json；全部章节位于统一正文，不设历史附录。','small')

page();text('本轮销毁、证据与限制','title')
data=[['对象 / 语言','销毁中位 ms','补满等待中位 ms']]
for product in order:
    for lang,label in languages.items():
        group=reference[(product,lang)]
        gates=[r['pool_after'] for r in group]
        value=fmt(statistics.median(g['elapsed_ms'] for g in gates)) if all(g['supported'] for g in gates) else '无等价池状态 API'
        data.append([names[product]+' / '+label,fmt(statistics.median(r['delete_ms'] for r in group)),value])
table(data,[220,130,160])
text('补满等待使用现有 50 ms 轮询，因此是客户端观测等待，不是补槽工作本身的 CPU 时间。所有 330 个模板创建正式样本须成功销毁；运行中 fork 的 30 个正式样本须两分支销毁完成。预检和被替换诊断批次留档，不纳入正式统计。','small')
text('原始证据：results/matrix/<语言>/<产品>/<模式>/01..10.json；results/live-formal/<语言>/01..10/result.json 和 host.log；native publication JSON；memory-preparation.json；source-provenance.json。README、计时埋点和测试脚本均保留在 113 的 staging/bench 工作区，本轮没有修改 108。','small')
text('启动全路径统计包含调度、RPC、持久化与解释器启动。开启了阶段诊断日志，因此结果代表本轮带诊断配置，不与无日志旧批次直接声称优化百分比。未实施生产强负载或大样本尾延迟验证。','small')

def footer(canvas,doc):
    canvas.setFont(FONT,8);canvas.setFillColor(NAVY)
    canvas.drawString(42,23,'113 / 本轮启动 n=10；完整资源批次 A 的口径见正文')
    canvas.drawRightString(A4[0]-42,23,str(doc.page))
path=OUT/'113-sixway-comprehensive-startup-modes-zh.pdf'
SimpleDocTemplate(str(path),pagesize=A4,rightMargin=42,leftMargin=42,
    topMargin=36,bottomMargin=40,title='113 六方综合报告：启动模式与运行中 fork',author='Benchmark research').build(story,onFirstPage=footer,onLaterPages=footer)
print(path)
