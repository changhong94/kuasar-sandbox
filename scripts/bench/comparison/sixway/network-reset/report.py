from pathlib import Path
import json,sys
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from plot_helpers import chart
B=Path(sys.argv[1]);out=B/'report';out.mkdir(exist_ok=True)
keys=['8','4','8-repeat'];ss={k:json.loads((B/k/'summary.json').read_text()) for k in keys}
rr={k:json.loads((B/k/'results/burst256/kuasar-fork/result.json').read_text()) for k in keys}
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'));story=[]
style=ParagraphStyle('body',fontName='STSong-Light',fontSize=10,leading=15,spaceAfter=9)
def p(t):story.append(Paragraph(t,style))
for en in (False,True):
 if en:story.append(PageBreak())
 def tr(a,b):return b if en else a
 p(tr('子 VM 网络身份重置修复与 256 并发验证','Child network identity reset: fix and 256-request validation'))
 p(tr('113 / sandbox_fork_staging。每组 64 个预备槽，独立重建模板和池，一次 warmup 不计入结果，随后同时释放 256 个客户端请求。从统一释放请求，到客户端收到新启动 Python 的随机 print 标识计时，包含解释器启动。成功实例全部保留，补满 64 槽后才开始统一销毁。','Host 113 / sandbox_fork_staging. Each group starts with 64 reserves, an independently rebuilt template/pool and one excluded warmup. 256 client workers are released together. Timing ends when the client receives a random print marker from a newly started Python interpreter. All successes remain alive until the batch ends and the reserve returns to 64.'))
 p('python:3.12-slim '+ss['8']['image_digest'])
 rows=[[tr('补槽路数','Workers'),tr('成功数','Success'),tr('全部 print / s','All print / s'),tr('全部 Ready / s','All Ready / s'),tr('补槽中位 / ms','Refill median / ms'),tr('补槽最大 / ms','Refill max / ms')]]
 for k,s in ss.items():rows.append([k,'256/256',f"{s['all_print_ms']/1000:.3f}",f"{s['all_ready_ms']/1000:.3f}",f"{s['refill_work_ms']['median']:.2f}",f"{s['refill_work_ms']['max']:.2f}"])
 t=Table([[Paragraph(str(x),style) for x in row] for row in rows],colWidths=[65,65,95,95,95,95]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4edf4')),('VALIGN',(0,0),(-1,-1),'TOP')]));story.append(t)
 p(tr('每组是一次完整突发，不将请求延迟分位数误当作多轮总耗时分位数。8-repeat 是额外稳定性复测。Ready 是执行通道内 shell 在启动 Python 前输出的标识被客户端收到；print 是随后 Python 输出；准备成本不计入请求耗时，另列如下。','Each group is one complete burst, not a distribution of repeated batch totals. 8-repeat is an additional stability run. Ready is receipt of a shell marker in the execution channel before Python starts; print is subsequent Python output. Preparation is reported separately.'))
 for k,s in ss.items():p(f"{k}: "+tr('服务启动到 64 槽就绪','Service start to 64 reserves')+f" {s['deployment']['service_to_ready_ms']/1000:.3f} s; "+tr('镜像模板准备及首次创建','Image-template preparation and first create')+f" {s['preparation']['template_prepare_publish_first_create_ms']/1000:.3f} s; "+tr('请求发出至重新补满 64 槽','Request release to 64 reserves replenished')+f" {s['full_reserve_after_request_release_ms']/1000:.3f} s.")
 p(tr('修复点：新身份的子 VM 不再触发原身份迁移重宣告，避免与 guest 网卡关闭发生锁等待；普通迁移仍保留重宣告。另补齐控制队列恢复扫描，仍在设备暂停屏障解除后才处理。没有延长 15 秒 RPC 截止时间，没有跳过网络身份或安全检查，持久化和 CoW 路径不变。','Fix: a child with a new identity no longer triggers inherited-identity migration announcements, avoiding contention with guest link-down. Ordinary migration keeps announcements. A separate control-queue restore scan runs after the device pause barrier. The 15-second RPC deadline, identity checks, persistence and CoW remain unchanged.'))
 p(tr('证据范围：捕获的失败栈为 virtnet_close → cancel_work_sync，发生在 link-down。驱动源码显示 config_work 重宣告会申请此时已被持有的 RTNL 锁。独立回归测试模拟待处理控制命令及丢失通知，旧代码失败、修复后通过；13 项设备测试、2 项身份重置测试和 82 项适配层测试通过。三轮共 768/768 成功。父子实时 fork、独立 MAC/IP、网关连通、持久化 QCOW2/ext4 写入隔离、两种销毁顺序均通过。','Evidence: the captured failure stack is virtnet_close → cancel_work_sync during link-down. Driver source shows announcement work takes RTNL, already held by link-down. A deterministic pending-control/lost-notification regression fails before and passes after the fix. 13 device tests, 2 identity-reset tests and 82 adapter tests pass. All 768 requests succeeded. Live-parent forks, distinct MAC/IP, gateway connectivity, persistent QCOW2/ext4 write isolation and both destruction orders pass.'))
 story.append(PageBreak())
 for typ in ('completion','gap','refill'):
  series=[]
  for k,col in zip(keys,['#236aa0','#d47921','#36804a']):
   if typ=='completion':values=[(i,v/1000) for i,v in enumerate(rr[k]['print']['completion_ms'],1)]
   elif typ=='gap':values=list(enumerate(rr[k]['print']['adjacent_completion_gap_ms'],2))
   else:
    ev=[json.loads(l) for l in (B/k/'results/burst256/kuasar-fork/pool-events.jsonl').read_text().splitlines()];ev=sorted([e for e in ev if e['event']=='prepared' and e.get('reason')=='refill'],key=lambda e:e['monotonic_ns']);values=[(i,e['elapsed_ms']) for i,e in enumerate(ev,1)]
   series.append((k,values,col))
  title={'completion':tr('Python print 完成时间线','Python print completion timeline'),'gap':tr('相邻完成间隔','Adjacent completion intervals'),'refill':tr('每次补槽实际准备耗时','Actual refill work per slot')}[typ]
  story.append(chart(series,title,'s' if typ=='completion' else 'ms',en,height=235,x_label=tr('完成序号','Completion rank')))
SimpleDocTemplate(str(out/'network-reset-zh-en.pdf'),pagesize=(595,842),leftMargin=40,rightMargin=40,topMargin=30,bottomMargin=30).build(story)
