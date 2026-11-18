from pathlib import Path
import json,math,statistics as st,sys,hashlib
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.graphics import renderSVG
B=Path(sys.argv[1]);O=B/'report';O.mkdir(exist_ok=True)
sys.path.insert(0,str(Path(__file__).resolve().parent));from plot_helpers import chart
r=json.loads((B/'results/burst256/kuasar-fork/result.json').read_text())
assert r['batch_valid'] and r['print']['completed']==256 and r['all_returned_instances_retained'] and r['all_private_files_verified'] and r['survivors_verified_after_half_destroyed'] and not r['public_remaining']
proof=json.loads((B/'disk-backing-verification.json').read_text());assert all(x['success'] for x in proof['rows']) and not proof['owned']
for name in ('warmup','01'):
 v=json.loads((B/f'live-fork-validation/python/{name}/result.json').read_text());assert v['success'] and not v['owned_remaining']
e=[json.loads(l) for l in (B/'results/burst256/kuasar-fork/pool-events.jsonl').read_text().splitlines()]
p=sorted([x for x in e if x['event']=='prepared' and x.get('reason')=='refill'],key=lambda x:x['monotonic_ns'])
s=sorted([x for x in e if x['event']=='prepare_started' and x.get('reason')=='refill'],key=lambda x:x['monotonic_ns'])
vac={x['sid']:x['monotonic_ns'] for x in e if x['event']=='vacated'}
assert len(p)==len(s)==len(vac)==256 and all(x['monotonic_ns']<r['cleanup_started_ns'] for x in p)
def stats(a):
 a=sorted(a);return {'n':len(a),'median':st.median(a),'p95':a[math.ceil(.95*len(a))-1],'p99':a[math.ceil(.99*len(a))-1],'max':a[-1]}
summary={'all_ready_ms':r['ready']['all_256_ms'],'all_print_ms':r['print']['all_256_ms'],'completion_gap_ms':stats(r['print']['adjacent_completion_gap_ms']),'refill_work_ms':stats([x['elapsed_ms'] for x in p]),'claim_to_refill_start_ms':stats([(x['monotonic_ns']-vac[x['vacancy_sid']])/1e6 for x in s]),'first_claim_to_first_refill_ms':(s[0]['monotonic_ns']-min(vac.values()))/1e6,'full_reserve_after_request_release_ms':(p[-1]['monotonic_ns']-r['start_ns'])/1e6,'full_reserve_after_last_print_ms':(p[-1]['monotonic_ns']-max(x['print_ns'] for x in r['requests']))/1e6,'requests':256,'successes':256,'refills_before_destroy':256,'held_pool':r['pool_while_instances_retained'],'image_digest':r['image_digest'],'client_dispatch_spread_ms':r['client_dispatch_spread_ms'],'preparation':json.loads((B/'preparation.json').read_text()),'deployment':json.loads((B/'deployment.json').read_text()),'peak_product_pss_mib':r['peak_retained_resources']['pss_mib']}
(B/'summary.json').write_text(json.dumps(summary,indent=2))
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
styles={k:ParagraphStyle(k,fontName='STSong-Light',fontSize=n,leading=n*1.5,spaceAfter=8,wordWrap='CJK') for k,n in [('title',18),('body',10),('small',8)]};story=[]
def txt(t,style='body'):story.append(Paragraph(t,styles[style]))
def table(rows):
 t=Table([[Paragraph(str(c),styles['small']) for c in row] for row in rows],colWidths=[140,90,90,90,90]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e4edf4')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t)
def f(x):return f'{x:,.2f}'
for en in (False,True):
 def tr(c,e):return e if en else c
 if story:story.append(PageBreak())
 txt(tr('fork：64 预备槽，256 并发创建','fork: 64 reserves, 256 concurrent creates'),'title')
 txt(tr('113 / sandbox_fork_staging / 本轮一次 256 请求突发测试，另有一次排除的 warmup。','Host 113 / sandbox_fork_staging / One 256-request burst plus one excluded warmup.'))
 txt(tr('256/256 创建、Ready、Python print 全部成功；全部成功实例保留到所有请求结束后才开始统一销毁。','All 256 calls reach create, Ready and Python print. Every instance is retained until all requests settle, then deleted.'))
 table([[tr('指标','Metric'),tr('数值','Value'),'','',''],[tr('全部 Ready','All Ready'),f(summary['all_ready_ms']/1000)+' s','','',''],[tr('全部 print','All print'),f(summary['all_print_ms']/1000)+' s','','',''],[tr('保留期间状态','Retained state'),'256 running','64 ready','320 owned',''],[tr('最后 print 后补满','Refill after last print'),f(summary['full_reserve_after_last_print_ms']/1000)+' s','','','']])
 txt(tr('时间起点：256 个客户端工作线程统一释放。Ready 为客户端收到 shell 随机标识；print 为收到新启动 Python 解释器输出的随机标识及换行，包含解释器启动。','Time zero is the common release of 256 client workers. Ready is receipt of a random shell marker; print is receipt of a random marker/newline from a newly started Python interpreter, including interpreter startup.'))
 txt('Python digest: '+r['image_digest'],'small')
 txt(tr('2 vCPU / 2 GiB；同一镜像与命令；无语言专用预热。客户端 FD 上限 8192，实测调用分发跨度 '+f(r['client_dispatch_spread_ms'])+' ms。','2 vCPU / 2 GiB; same image and command; no language-specific prewarming. Client FD limit 8192; measured call-dispatch spread '+f(r['client_dispatch_spread_ms'])+' ms.'))
 txt(tr('容量语义：已领取实例不占预备容量。领取事务持久化成功后唤醒补槽；绑定期间仍私有，完成安全屏障后才发布。新槽使用独立 VM 和网络身份，不复用运行实例。','Capacity counts unclaimed reserves. Durable assignment wakes refill; binding stays private until publication barriers complete. Replacements get separate VMs/network identities; running instances are not recycled.'))
 txt(tr('验证：256 个独立 IP/命名空间/holder；256 份独立 fsync 文件；先销毁一半后其余文件和执行仍正确；最后无实例残留，64 槽就绪。运行中父沙箱 fork 的进程继续运行、磁盘独立写入与两种销毁顺序也通过。','Validation: 256 distinct IPs/namespaces/holders; independent fsynced files; survivors retain correct files/execution after half are deleted; final inventory empty with 64 reserves ready. Live-parent fork preserves process progress, independent disk writes and both deletion orders.'))
 story.append(PageBreak());txt(tr('创建完成时间与相邻完成间隔','Completion timeline and adjacent intervals'),'title')
 graphs=[('completion-timeline',[(i,t/1000) for i,t in enumerate(r['print']['completion_ms'],1)],tr('Python print 完成时间','Python print completion'),tr('请求发出后的实际耗时 / 秒','Elapsed since release / seconds')),('completion-intervals',list(enumerate(r['print']['adjacent_completion_gap_ms'],2)),tr('相邻两次完成的时间间隔','Adjacent completion intervals'),tr('间隔 / ms','Interval / ms'))]
 for name,values,title,ylabel in graphs:
  d=chart([('fork (256/256)',values,'#236aa0')],title,ylabel,en,height=255);story.append(d);story.append(Spacer(1,12))
  if not en:renderSVG.drawToFile(d,str(O/(name+'.svg')))
 m=summary['completion_gap_ms'];table([[tr('255 个完成间隔 / ms','255 completion intervals / ms'),'Median','P95','P99','Max'],[tr('本批次分布','This burst'),*[f(m[k]) for k in ('median','p95','p99','max')]]])
 txt(tr('横轴为按 print 完成排序的请求序号；间隔从第 2 个完成开始。没有把失败或缺失结果填为零。分位数描述这一批次的间隔，不是重复 256 次突发实验。','X is rank by print completion; intervals start at rank 2. No missing/failed results are zero-filled. Percentiles describe gaps within this burst, not repeated burst experiments.'),'small')
 story.append(PageBreak());txt(tr('领取后补槽：实际工作与排队','Refill after assignment: work and queueing'),'title')
 d=chart([('fork',list(enumerate([x['elapsed_ms'] for x in p],1)),'#236aa0')],tr('256 次实际补槽耗时','Actual preparation time for 256 refills'),tr('准备耗时 / ms','Preparation work / ms'),en,height=300,x_label=tr('完成的第几个补槽','Refill completion rank'));story.append(d)
 if not en:renderSVG.drawToFile(d,str(O/'refill-times.svg'))
 rows=[[tr('指标 / ms','Metric / ms'),'Median','P95','P99','Max']]
 for key,label in [('refill_work_ms',tr('实际准备工作','Actual preparation work')),('claim_to_refill_start_ms',tr('领取提交到开始准备','Durable claim to prep start'))]:rows.append([label,*[f(summary[key][k]) for k in ('median','p95','p99','max')]])
 table(rows)
 txt(tr('首次领取提交后 '+f(summary['first_claim_to_first_refill_ms'])+' ms 即开始补槽。补槽为串行工作线程；后续排队来自前面的实际准备工作，并非固定冷却期。256 次补槽全部在销毁前完成。','First refill starts '+f(summary['first_claim_to_first_refill_ms'])+' ms after the first durable claim. A serial worker performs refill; later queueing is actual preceding work, not a fixed cooldown. All 256 refills complete before deletion.'))
 txt(tr('从发出请求到全部实例运行且 64 槽补满：'+f(summary['full_reserve_after_request_release_ms']/1000)+' 秒。此时进程 PSS 合计 '+f(summary['peak_product_pss_mib'])+' MiB（含专属控制面，不含大部分内核内存和未映射页缓存）。','From release to all instances running plus 64 ready reserves: '+f(summary['full_reserve_after_request_release_ms']/1000)+' seconds. Product-process PSS is '+f(summary['peak_product_pss_mib'])+' MiB, including dedicated controllers but excluding most kernel memory/unmapped page cache.'))
 txt(tr('准备成本单列：服务启动到 64 槽就绪 '+f(summary['deployment']['service_to_ready_ms']/1000)+' 秒；镜像模板准备、发布与首次创建 '+f(summary['preparation']['template_prepare_publish_first_create_ms']/1000)+' 秒，该阶段未启动 Python 解释器。','Separate preparation: service start to 64 ready reserves '+f(summary['deployment']['service_to_ready_ms']/1000)+' seconds; image-template preparation, publication and first create '+f(summary['preparation']['template_prepare_publish_first_create_ms']/1000)+' seconds, without launching Python.'))
 txt(tr('持久化、隔离屏障及 CoW 路径保留。原始结果：113 /home/hong/src/research/pool-capacity-113；未修改 108。','Persistence, isolation barriers and CoW remain. Raw results: host 113 /home/hong/src/research/pool-capacity-113. Host 108 is untouched.'),'small')
SimpleDocTemplate(str(O/'fork-pool-256-zh-en.pdf'),rightMargin=42,leftMargin=42,topMargin=36,bottomMargin=36,title='fork 256 concurrent creates / 64 reserve slots',author='Sandbox benchmark').build(story)
