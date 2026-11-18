from pathlib import Path
import json,sys,statistics,math
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,PageBreak
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from plot_helpers import chart
B=Path(sys.argv[1]);out=B/'report';out.mkdir(exist_ok=True);keys=['8','16','32','64']
ss={k:json.loads((B/k/'summary.json').read_text()) for k in keys};rr={k:json.loads((B/k/'results/burst256/kuasar-fork/result.json').read_text()) for k in keys}
ev={k:[json.loads(l) for l in (B/k/'results/burst256/kuasar-fork/pool-events.jsonl').read_text().splitlines()] for k in keys}
for k in keys:
 r=rr[k];assert r['batch_valid'] and r['print']['completed']==256 and r['failed_requests']==0 and r['all_private_files_verified'] and r['survivors_verified_after_half_destroyed'] and r['cleanup_quiescence_verified'] and not r['public_remaining']
 assert r['pool_while_instances_retained']['ready']==64 and r['pool_while_instances_retained']['assigned']==256
 intervals=[]
 for e in ev[k]:
  if e.get('reason')=='refill' and e['event'] in ('prepare_started','prepared'):intervals.append((e['monotonic_ns'],1 if e['event']=='prepare_started' else -1))
 active=maximum=0
 for _,d in sorted(intervals):active+=d;maximum=max(active,maximum)
 assert active==0
 ss[k]['observed_peak_refill_concurrency']=maximum
(B/'comparison.json').write_text(json.dumps(ss,indent=2))
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'));story=[]
style=ParagraphStyle('body',fontName='STSong-Light',fontSize=9,leading=14,spaceAfter=8)
def p(t):story.append(Paragraph(t,style))
def table(rows,widths):
 t=Table([[Paragraph(str(x),style) for x in row] for row in rows],colWidths=widths);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4edf4')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t)
for en in (False,True):
 if en:story.append(PageBreak())
 def tr(a,b):return b if en else a
 p(tr('网络超时修复后：8 / 16 / 32 / 64 路补槽比较','After the network-timeout fix: 8 / 16 / 32 / 64 refill workers'))
 p(tr('113 / sandbox_fork_staging。同一代码和二进制，每组 64 个预备槽，独立重建模板和池，先做 1 次不计入结果的 warmup，再同时释放 256 个客户端创建请求。计时从统一释放请求开始，到客户端收到新启动 Python 的随机 print 标识结束，包含解释器启动；不做语言专用预热。每组只有一次突发，总耗时不是多轮中位数。','Host 113 / sandbox_fork_staging. Identical source and binaries; 64 reserves per group. Each independently rebuilds the template and pool, performs one excluded warmup, then releases 256 client creation requests together. Timing ends at receipt of a random print marker from a newly started Python interpreter, including interpreter startup. No language-specific prewarming. One burst per group; batch totals are not medians of repeated runs.'))
 p('python:3.12-slim '+ss['8']['image_digest'])
 rows=[[tr('配置路数','Workers'),tr('成功数','Success'),tr('全部 print / s','All print / s'),tr('相对 8 路耗时变化','Time change vs 8'),tr('观测最大并行','Observed max active'),tr('重新补满 / s','Full reserves / s')]]
 for k,s in ss.items():rows.append([k,'256/256',f"{s['all_print_ms']/1000:.3f}",f"{(s['all_print_ms']/ss['8']['all_print_ms']-1)*100:+.1f}%",s['observed_peak_refill_concurrency'],f"{s['full_reserve_after_request_release_ms']/1000:.3f}"])
 table(rows,[55,65,90,100,90,110])
 p(tr('“重新补满”与 print 使用同一请求释放起点，表示 256 个成功实例仍保留时，预备池恢复为 64 槽。配置路数是上限，实际并行还受可补槽数量与内部阶段限制。','Full reserves uses the same request-release origin and ends when 64 reserves are replenished while all 256 successful sandboxes remain alive. Configured workers are an upper limit; actual concurrency also depends on vacancies and internal stages.'))
 rows=[[tr('路数','Workers'),tr('完成间隔中位 / ms','Gap median / ms'),tr('间隔 P95 / ms','Gap P95 / ms'),tr('间隔最大 / ms','Gap max / ms'),tr('补槽中位 / ms','Refill median / ms'),tr('补槽最大 / ms','Refill max / ms')]]
 for k,s in ss.items():
  g=s['completion_gap_ms'];f=s['refill_work_ms'];rows.append([k,*[f'{v:.2f}' for v in (g['median'],g['p95'],g['max'],f['median'],f['max'])]])
 table(rows,[45,100,90,90,90,95])
 p(tr('完成间隔：按客户端收到 print 的时刻排序，相邻两次完成之差，共 255 个间隔，不包含第 1 次完成前的等待。补槽耗时：每个补槽工作从开始执行到槽就绪，包含持久化及网络身份处理；排队等待单列于原始 summary.json。','Completion gaps are the 255 differences between adjacent print receipt times, excluding the wait before the first completion. Refill work runs from execution start to slot readiness, including persistence and network identity handling; queue waits are separately available in summary.json.'))
 p(tr('准备成本（不计入请求耗时，以下数值不得直接相加）：','Preparation costs (outside request timing; these values should not simply be added):'))
 for k,s in ss.items():p(f"{k}: "+tr('服务启动至 64 槽就绪','Service start to 64 reserves')+f" {s['deployment']['service_to_ready_ms']/1000:.3f} s; "+tr('镜像模板准备与首次创建','Image-template preparation and first create')+f" {s['preparation']['template_prepare_publish_first_create_ms']/1000:.3f} s; "+tr('保留期间产品进程 PSS','Product-process PSS during retention')+f" {s['peak_product_pss_mib']:.1f} MiB.")
 p(tr('每组 256 个实例全部保留到结束；验证独立持久化文件，删除一半后检查剩余实例继续执行及文件状态，再删除其余实例，确认没有遗留测试实例。持久化、安全屏障、CoW 和 RPC 截止时间保持不变。','All 256 instances are retained through completion. Independent persistent files are verified; after half are deleted, survivors execute commands and retain their own files, then the rest are deleted and cleanup checked. Persistence, safety barriers, CoW and RPC deadlines are unchanged.'))
 story.append(PageBreak())
 for typ in ('completion','gap','refill'):
  series=[]
  for k,col in zip(keys,['#236aa0','#d47921','#36804a','#8a59a8']):
   if typ=='completion':values=list(enumerate([v/1000 for v in rr[k]['print']['completion_ms']],1))
   elif typ=='gap':values=list(enumerate(rr[k]['print']['adjacent_completion_gap_ms'],2))
   else:values=[(i,e['elapsed_ms']) for i,e in enumerate(sorted([e for e in ev[k] if e['event']=='prepared' and e.get('reason')=='refill'],key=lambda e:e['monotonic_ns']),1)]
   series.append((k,values,col))
  title={'completion':tr('Python print 完成时间线','Python print completion timeline'),'gap':tr('相邻完成间隔','Adjacent completion gaps'),'refill':tr('每次补槽实际准备耗时','Actual refill work per slot')}[typ]
  story.append(chart(series,title,'s' if typ=='completion' else 'ms',en,height=235,x_label=tr('完成序号','Completion rank')))
SimpleDocTemplate(str(out/'refill-scale-zh-en.pdf'),pagesize=(595,842),leftMargin=40,rightMargin=40,topMargin=30,bottomMargin=30).build(story)
