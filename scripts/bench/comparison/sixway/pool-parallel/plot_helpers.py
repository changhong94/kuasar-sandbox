"""Vector plots from the retained 256-request burst, without zero-padding failures."""
from pathlib import Path
import datetime,json,math,statistics
from reportlab.graphics.shapes import Drawing,String,Line
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderSVG
from reportlab.lib import colors
ORDER=['kuasar-fork','kuasar-mlink','agentenv','cube','kuasar-off','kuasar-uffd']
NAMES=dict(zip(ORDER,['fork','mlink','AgentENV','CubeSandbox','Kuasar off','Kuasar UFFD']))
COLORS=['#236aa0','#d47921','#36804a','#58616a','#8a59a8','#bc4450']
def read(base):
 rows={p:json.loads((base/f'results/burst256/{p}/result.json').read_text()) for p in ORDER}
 assert all(r['batch_valid'] and not r['public_remaining'] and len(r['requests'])==256 for r in rows.values())
 return rows

def chart(series,title,y_label,english=False,height=285,x_label=None,xmax=256):
 d=Drawing(510,height);plot=LinePlot();plot.x=55;plot.y=56;plot.width=440;plot.height=height-110
 available=[(name,values,color) for name,values,color in series if values]
 if not available:
  d.add(String(55,height/2,'No refill events' if english else '没有补槽事件',fontName='STSong-Light',fontSize=11));return d
 plot.data=[values for _,values,_ in available]
 ymax=max(y for _,values,_ in available for _,y in values);ymax=max(1,ymax*1.08)
 plot.xValueAxis.valueMin=1;plot.xValueAxis.valueMax=max(2,xmax);plot.xValueAxis.valueStep=max(1,math.ceil(xmax/8))
 plot.yValueAxis.valueMin=0;plot.yValueAxis.valueMax=ymax;plot.yValueAxis.valueStep=ymax/5
 plot.xValueAxis.labels.fontName='Helvetica';plot.xValueAxis.labels.fontSize=7
 plot.yValueAxis.labels.fontName='Helvetica';plot.yValueAxis.labels.fontSize=7
 plot.yValueAxis.labelTextFormat='%.1f';plot.yValueAxis.visibleGrid=True;plot.yValueAxis.gridStrokeColor=colors.HexColor('#e1e5e8')
 for i,(_,_,color) in enumerate(available):plot.lines[i].strokeColor=colors.HexColor(color);plot.lines[i].strokeWidth=1
 d.add(plot);d.add(String(0,height-13,title,fontName='STSong-Light',fontSize=11));d.add(String(0,height-31,y_label,fontName='STSong-Light',fontSize=8))
 d.add(String(170,34,x_label or ('Completion rank' if english else '完成的第几个请求'),fontName='STSong-Light',fontSize=8))
 for i,(name,_,color) in enumerate(available):
  x=8+(i%3)*170;y=18-(i//3)*13;d.add(Line(x,y+2,x+15,y+2,strokeColor=colors.HexColor(color),strokeWidth=2));d.add(String(x+19,y,name,fontName='STSong-Light',fontSize=7))
 return d

def startup_charts(base,english=False):
 rows=read(base);series=[];gaps=[]
 for p,color in zip(ORDER,COLORS):
  r=rows[p];label=NAMES[p]+f" ({r['print']['completed']}/256)"
  series.append((label,[(i,t/1000) for i,t in enumerate(r['print']['completion_ms'],1)],color))
  gaps.append((label,[(i,t) for i,t in enumerate(r['print']['adjacent_completion_gap_ms'],2)],color))
 return [chart(series,'Print completion timeline' if english else 'Python print 完成时间线','Seconds since simultaneous release' if english else '距统一发出请求的实际耗时 / 秒',english),chart(gaps,'Intervals between adjacent print completions' if english else '相邻两次 Python print 完成之间的间隔','Interval / ms' if english else '时间间隔 / ms',english)]

def refill_data(base):
 result={}
 for product in ('kuasar-fork','kuasar-mlink'):
  r=json.loads((base/f'results/burst256/{product}/result.json').read_text());events=[]
  for line in (base/f'results/burst256/{product}/pool-events.jsonl').read_text().splitlines():
   try:e=json.loads(line)
   except ValueError:continue
   if product=='kuasar-fork':
    if e.get('event')!='prepared' or e.get('reason')!='refill':continue
    end=e['monotonic_ns'];duration=e['elapsed_ms'];phase='after_cleanup_started' if end>=r['cleanup_started_ns'] else 'before_cleanup';sort=end
   else:
    fields=e.get('fields',{})
    if fields.get('event')!='runtime_slot_prepare_execution' or not fields.get('success'):continue
    end=int(datetime.datetime.fromisoformat(e['timestamp'].replace('Z','+00:00')).timestamp()*1e9);duration=fields['total_us']/1000;phase='after_cleanup_started' if end>=r['cleanup_started_unix_ns'] else 'before_cleanup';sort=fields['finished_mono_us']
   events.append({'sort':sort,'duration_ms':duration,'phase':phase})
  events.sort(key=lambda e:e['sort'])
  result[product]={'events':events,'during_retained_request_window':sum(e['phase']=='before_cleanup' for e in events),'after_cleanup_started':sum(e['phase']=='after_cleanup_started' for e in events),'median_work_ms':statistics.median(e['duration_ms'] for e in events) if events else None,'max_work_ms':max((e['duration_ms'] for e in events),default=None)}
 return result

def refill_chart(base,english=False):
 rows=refill_data(base);series=[]
 for p,color in zip(('kuasar-fork','kuasar-mlink'),COLORS):series.append((NAMES[p],[(i,e['duration_ms']) for i,e in enumerate(rows[p]['events'],1)],color))
 return chart(series,'Measured VM-slot refill work' if english else '每次 VM 补槽的实际准备耗时','Preparation work / ms' if english else '实际准备耗时 / ms',english,height=310,x_label='Refill completion rank' if english else '完成的第几个补槽',xmax=max(2,max(len(r['events']) for r in rows.values())))
