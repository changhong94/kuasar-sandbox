from pathlib import Path
import json,sys
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.graphics import renderSVG
from plot_helpers import chart
B=Path(sys.argv[1]);out=B/'report';out.mkdir(exist_ok=True);s=json.loads((B/'comparison.json').read_text())
raw={n:json.loads((B/n/'results/burst256/kuasar-fork/result.json').read_text()) for n in s}
events={n:[json.loads(l) for l in (B/n/'results/burst256/kuasar-fork/pool-events.jsonl').read_text().splitlines()] for n in s}
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'));story=[]
styles={k:ParagraphStyle(k,fontName='STSong-Light',fontSize=size,leading=size*1.45,spaceAfter=8,wordWrap='CJK') for k,size in [('title',18),('body',10),('small',8)]}
def txt(t,k='body'):story.append(Paragraph(t,styles[k]))
def tab(r,w):
 t=Table([[Paragraph(str(c),styles['small']) for c in row] for row in r],colWidths=w);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4edf4')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t)
def f(v):return '—' if v is None else f'{v:,.2f}'
for en in (False,True):
 def tr(a,b):return b if en else a
 if story:story.append(PageBreak())
 txt(tr('补槽并发比较：8 / 16 / 32 / 64','Refill concurrency: 8 / 16 / 32 / 64'),'title')
 txt(tr('113 / sandbox_fork_staging；每组 64 个预备槽，排除一次 warmup，然后同时发出 256 个请求。保留全部成功实例至结束后统一销毁。各组独立重建模板和池，未做语言专用预热。','Host 113 / sandbox_fork_staging; 64 reserves per group, one excluded warmup, then 256 simultaneous requests. All successes retained until batch end before deletion. Each group independently rebuilds its template and pool, without language-specific prewarming.'))
 txt('python:3.12-slim '+s['8']['image_digest'],'small')
 txt(tr('从统一释放客户端线程，到收到新启动 Python 的随机 print 标识计时，包含解释器启动。每组一次突发；8-repeat 为异常后的独立复测。未修改超时或安全屏障。','Timed from common client-worker release to a random print marker from a newly started Python interpreter, including startup. One burst per group; 8-repeat is an independent follow-up after failures. Timeouts and safety barriers are unchanged.'))
 tab([[tr('补槽线程','Workers'),tr('成功数','Successes'),tr('全部 256 完成 / s','All 256 / s'),tr('最后成功 / s','Last success / s'),tr('全部请求结束 / s','All settled / s')]]+[[n,str(x['successes'])+'/256',f(x['all_print_s']),f(x['last_success_s']),f(x['all_requests_settled_s'])] for n,x in s.items()],[70,90,110,110,120])
 txt(tr('“全部 256 完成”只在 256/256 成功时给数值；“最后成功”不含失败请求，不能当作整批完成时间。“全部请求结束”包含错误和超时。失败轮不会被隐藏或用复测替换。','“All 256” is populated only for 256/256 successes. “Last success” excludes failed calls and is not whole-batch completion. “All settled” includes errors/timeouts. Failed runs remain visible and are never replaced by retests.'))
 errors={k:x['errors'] for k,x in s.items() if x['errors']}
 txt(tr('已观察到的错误：','Observed errors:')+' reset child network: ttrpc err: Receive packet timeout Elapsed(())。','small')
 txt(tr('错误发生在子 VM 网络身份重置阶段。现有日志能定位失败阶段，但尚不足以确认内部根因；不能把全部延迟差异简单归因于补槽线程数。','Failures occur during child-VM network identity reset. Logs identify the failing stage but do not establish its internal root cause; timing differences cannot be attributed solely to refill-worker count.'))
 tab([[tr('线程','Workers'),tr('补槽中位 ms','Refill median ms'),tr('补槽 P95 ms','Refill P95 ms'),tr('补槽最大 ms','Refill max ms'),tr('在途峰值','Peak active')]]+[[n,f(x['refill_work_ms']['median']),f(x['refill_work_ms']['p95']),f(x['refill_work_ms']['max']),x['peak_inflight']] for n,x in s.items()],[70,110,110,110,100])
 txt(tr('各组独立事件文件均记录 256 次补槽。这里是开始准备到 Ready 发布的实际耗时，不含等待补槽线程的排队。实际并发还受容量预留约束。','Separate event files record 256 refills per group. Work duration runs from preparation start through Ready publication and excludes queueing for a worker. Capacity reservation also constrains actual concurrency.'),'small')
 story.append(PageBreak());txt(tr('完成与补槽曲线','Completion and refill curves'),'title')
 palette=['#236aa0','#d47921','#36804a','#8a59a8','#777777']
 graphs=[('completion-timeline',tr('成功请求的 Python print 完成时间','Python print completion of successful calls'),tr('实际耗时 / 秒','Elapsed / seconds'),{n:list(enumerate([t/1000 for t in raw[n]['print']['completion_ms']],1)) for n in s}),('completion-intervals',tr('相邻成功完成之间的间隔','Adjacent successful completion gaps'),tr('间隔 / ms','Gap / ms'),{n:list(enumerate(raw[n]['print']['adjacent_completion_gap_ms'],2)) for n in s}),('refill-times',tr('每次补槽的实际准备耗时','Actual preparation work per refill'),tr('实际耗时 / ms','Elapsed / ms'),{n:list(enumerate([e['elapsed_ms'] for e in sorted(events[n],key=lambda e:e['monotonic_ns']) if e['event']=='prepared' and e['reason']=='refill'],1)) for n in s})]
 for name,title,ylabel,data in graphs:
  d=chart([(n+' ('+str(s[n]['successes'])+'/256)',data[n],color) for n,color in zip(s,palette)],title,ylabel,en,height=210,x_label=tr('补槽完成序号','Refill completion rank') if name=='refill-times' else None);story.append(d)
  if not en:renderSVG.drawToFile(d,str(out/(name+'.svg')))
 txt(tr('完成曲线在实际成功数处结束，不把失败补成 256 个成功点；补槽曲线每组均有 256 点。','Completion curves stop at the actual success count; failures are never padded to 256 successes. Every refill curve has 256 points.'),'small')
 story.append(PageBreak());txt(tr('准备成本、资源与清理验证','Preparation, resources and cleanup validation'),'title')
 tab([[tr('线程','Workers'),tr('服务到 64 槽 / s','Service to 64 / s'),tr('镜像准备 / s','Image prep / s'),tr('保留实例 / 个','Retained users'),tr('产品 PSS / MiB','Product PSS / MiB')]]+[[n,f(x['service_prepare_s']),f(x['image_prepare_s']),x['held_pool']['assigned'],f(x['pss_mib'])] for n,x in s.items()],[70,110,110,100,110])
 txt(tr('服务准备与镜像模板准备单独计时，不计入创建突发。各组 PSS 统计成功实例全部保留且 64 个预备槽补满后的产品进程内存，包含专属控制面，不含大部分内核内存及未映射页缓存；成功数不同，不能直接作为等规模内存比较。','Service and image-template preparation are separate from burst timing. PSS covers product processes after retaining all successes and replenishing 64 reserves, including dedicated controllers but excluding most kernel memory/unmapped page cache. Success counts differ, so these are not equal-scale memory comparisons.'))
 tab([[tr('线程','Workers'),tr('相邻间隔中位 ms','Gap median ms'),tr('相邻间隔 P95 ms','Gap P95 ms'),tr('相邻间隔最大 ms','Gap max ms')]]+[[n,f(x['completion_gap_ms']['median']),f(x['completion_gap_ms']['p95']),f(x['completion_gap_ms']['max'])] for n,x in s.items()],[70,140,140,150])
 txt(tr('所有成功实例均验证独立 fsync 文件；删除一半后剩余实例继续执行且文件内容正确；清理后用户实例为零且 64 槽就绪。失败请求明确计入失败数，不宣称 256/256 通过。','All successful instances pass independent fsynced-file validation; survivors execute with correct files after half are deleted. Final user inventory is empty with 64 reserves ready. Failed calls remain failures; no claim of 256/256 passing is made for partial runs.'))
 txt(tr('仅将允许的补槽线程上限从 32 扩展到 64，默认值仍为 8。持久化、安全屏障及 CoW 保留，未修改 108 或其他人的进程。','Only the configurable worker limit was raised from 32 to 64; default remains 8. Persistence, safety barriers and CoW remain; host 108 and other users’ processes are untouched.'))
 txt('/home/hong/src/research/pool-workers-113','small')
SimpleDocTemplate(str(out/'refill-workers-zh-en.pdf'),leftMargin=42,rightMargin=42,topMargin=36,bottomMargin=36).build(story)
