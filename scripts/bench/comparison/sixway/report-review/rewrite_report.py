from pathlib import Path
B=Path(__file__).parent
s=(B/'report-original.py').read_text()
s=s.replace("assert load(B/'burst256-complete.json')['retained_until_all_requests_settled']\nimport burst_charts\nbursts=burst_charts.read(B)","assert load(B/'paced-complete.json')['complete']\nimport paced_charts as charts\nbursts=charts.read(B)\npaced={i:charts.read(B,i) for i in charts.INTERVALS}\nfailure_evidence=load(B/'failure-analysis.json')")
s=s.replace("for english in (False,True):\n",(B/'report-summary.block').read_text()+"\nfor english in (False,True):\n summary_page()\n",1)
s=s.replace('全部测量来自本次 113 正式批次。','启动、并发、资源和持久化测量来自本次 113 正式批次；隔离宿主重启功能验证单独标明范围。').replace('All measurements come from this formal study on host 113.','Startup, concurrency, resources and persistence are measured in this formal study on host 113; isolated-host reboot validation is identified separately.')
s=s.replace('代码在 sandbox_fork_staging；未修改 108 的优化分支。准备成本与启动请求内耗时分开列。','准备与补槽均为 8 路，运行容量与预备池分开配置。').replace('Code is on sandbox_fork_staging; the 108 optimization branch is untouched. Preparation is reported separately from request latency.','Preparation and refill both use eight workers; running capacity is separate from the reserve pool.')
s=s.replace("  table(rr,[90,65,88,88,88,91])","  story.append(charts.bars([(names[p],st.median(x['ready_ms'] for x in group(p,l,reference(p))),st.median(x['print_ms'] for x in group(p,l,reference(p)))) for p in order],tr('Ready 与 print 中位数','Median Ready and print'),english,height=220))\n  table(rr,[90,65,88,88,88,91])")
a=s.index("  rr=[head(tr('对象 / 模式','Product / mode'))]")
z=s.index("  text('fork 的 remote",a)
s=s[:a]+'''  text('单位 ms；图用对数刻度同时展示几十毫秒与数秒，百分比以数字计算。每组 50 次。','Units: ms; log scale shows tens of milliseconds and seconds together. Percentages use the numeric values. Fifty samples per group.',style='small')
  modes=('local_warm','local_cold','remote');ps=('kuasar-fork','kuasar-off','kuasar-uffd')
  labels={'local_warm':'warm','local_cold':'cold','remote':'chunk'}
  story.append(charts.bars([(names[p]+' / '+labels[m],st.median(x['ready_ms'] for x in group(p,l,m)),st.median(x['print_ms'] for x in group(p,l,m))) for m in modes for p in ps],tr('同一镜像，不同恢复路径','Same image, different restore paths'),english,log=True,height=295))
  rr=[[tr('对象 / 模式','Product / mode'),'Ready '+tr('中位','median'),'print '+tr('中位','median'),'print P95','print P99',tr('print 最大','print max')]]
  for m in modes:
   for p in ps:
    a=group(p,l,m);rr.append([names[p]+' / '+labels[m],f(st.median(x['ready_ms'] for x in a))]+[f(v) for v in stats([x['print_ms'] for x in a])])
  table(rr,[140,74,74,74,74,74])
  text(tr('按 print 中位数，fork 相对 UFFD：','fork relative to UFFD, median print: ')+', '.join(labels[m]+' '+f((st.median(x['print_ms'] for x in group('kuasar-fork',l,m))/st.median(x['print_ms'] for x in group('kuasar-uffd',l,m))-1)*100)+'%' for m in modes)+tr('（负数表示更短）。',' (negative means shorter).'),style='small')
'''+s[z:]
a=s.index(" page('同时创建 256")
z=s.index(" page('chunk 数据来源",a)
s=s[:a]+(B/'report-paced.block').read_text()+s[z:]
# Non-timing memory/storage pages are Python-only, including startup-side storage observations.
a=s.index(" page('chunk 数据来源")
z=s.index(" page('准备与发布成本",a)
part=s[a:z].replace('for l in langs:',"for l in ('python',):").replace("for r in capacity['rows']:rr.append", "for r in (v for v in capacity['rows'] if v['language']=='python'):rr.append")
s=s[:a]+part+s[z:]
a=s.index(" page('准备与发布成本'")
z=s.index(" for l,label in langs.items():",a)
s=s[:a]+s[z:]
s=s.replace(" for l,label in langs.items():\n  g=live[l]", " for l,label in [('python','Python')]:\n  g=live[l]")
s=s.replace("events=row['spans'];lanes=list(dict.fromkeys(x['lane'] for x in events));end=max(x['end_ms'] for x in events)","events=row['spans'];lanes=list(dict.fromkeys(x['lane'] for x in events));end=max(row['print_ms'],max(x['end_ms'] for x in events))*1.04")
s=s.replace("from reportlab.graphics.shapes import Drawing,Rect,Line,String","from reportlab.graphics.shapes import Drawing,Rect,Line,String,Circle")
s=s.replace("h=len(tracks)*26+48", "h=len(tracks)*24+80").replace("h-49-i*26", "h-67-i*24")
s=s.replace(" d.add(String(455,0,tr('请求后 / ms'", """ for key,color,yy in [('ready_ms','#bc4450',h-30),('print_ms','#6e4d9b',h-43)]:
  x=left+row[key]/end*w;d.add(Line(x,23,x,h-47,strokeColor=colors.HexColor(color),strokeWidth=1,strokeDashArray=[3,2]));d.add(Circle(x,h-62,3,fillColor=colors.HexColor(color),strokeColor=None))
  label=(tr('子 Ready','Child Ready') if key=='ready_ms' else tr('子 print','Child print'))+' '+f(row[key])+' ms'
  d.add(String(min(x-35,405),yy,label,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=8,fillColor=colors.HexColor(color)))
 d.add(String(455,0,tr('请求后 / ms'""")
s=s.replace("  page(label+'：最长样本及阶段说明'", """  page(label+'：代表样本阶段明细',label+': representative-sample phase details')
  phase_table(g['representative'])
  text('各行是同一个真实请求的时间区间，可重叠，不能直接相加。Ready 与 print 的绝对位置同时标在时间图中。','Rows describe one real request and may overlap; do not add them. Absolute Ready and print positions are also marked on the timeline.','small')
  page(label+'：最长样本及阶段说明'""")
s=s.replace("  table(rr,[95,135,145,135])", """  table(rr,[95,135,145,135])
  aa=resource['products']['kuasar-fork']['storage'][kind];bb=resource['products']['kuasar-mlink']['storage'][kind]
  text(tr('fork / mlink 相对差异：运行磁盘 ','fork / mlink differences: running disk ')+pct(aa['live2']['extent_mib'],bb['live2']['extent_mib'])+tr('，保存后磁盘 ','; saved disk ')+pct(aa['paused2']['extent_mib'],bb['paused2']['extent_mib'])+tr('，运行 PSS ','; running PSS ')+pct(aa['live2']['pss_mib'],bb['live2']['pss_mib']),style='small')""")
a=s.index(" page('64 槽准备、销毁与补满'")
z=s.index("\ndef footer",a)
s=s[:a]+(B/'report-pool.block').read_text()+s[z:]
s=s.replace("'113 · sandbox_fork_staging · report-revision-113'","'Host 113 | Six-product study | 2026-11'")
s=s.replace('本次两轮真实嵌套 Linux 宿主重置','独立功能验证批次的两轮真实嵌套 Linux 宿主重置').replace('Two fresh real nested-Linux host resets','Two real nested-Linux host resets in the separately recorded functional-validation batch')
s=s.replace("SimpleDocTemplate(str(O/'sandbox-sixway-zh-en.pdf')", """class ReportDoc(SimpleDocTemplate):
 def afterFlowable(self,flowable):
  if isinstance(flowable,Paragraph) and flowable.style.name=='title':
   key='section-'+str(self.page)+'-'+str(len(getattr(self,'section_keys',[])))
   self.section_keys=getattr(self,'section_keys',[])+[key]
   self.canv.bookmarkPage(key);self.canv.addOutlineEntry(flowable.getPlainText(),key,level=0,closed=False)
ReportDoc(str(O/'sandbox-sixway-zh-en.pdf')""")
# Use a Latin font for the English section; create separate style objects so
# the already-built Chinese paragraphs retain their CJK font.
s=s.replace("for english in (False,True):\n", "for english in (False,True):\n styles={n:ParagraphStyle(n,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=size,leading=leading,textColor=NAVY,spaceAfter=7,wordWrap=('LTR' if english else 'CJK')) for n,size,leading in [('title',19,26),('heading',12,18),('body',9.5,15),('small',7.7,11)]}\n")
s=s.replace("fontName='STSong-Light'", "fontName=('Helvetica' if english else 'STSong-Light')")
s=s.replace('−','-')
(B/'report.py').write_text(s)
