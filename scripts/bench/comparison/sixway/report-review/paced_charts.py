"""One observed batch per pacing interval; no fabricated completion points."""
from pathlib import Path
import datetime,json,math,statistics,collections,re
from reportlab.graphics.shapes import Drawing,String,Line,Rect
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.lib import colors
ORDER=['kuasar-fork','kuasar-mlink','agentenv','cube','kuasar-off','kuasar-uffd']
NAMES=dict(zip(ORDER,['fork','mlink','AgentENV','CubeSandbox','Kuasar off','Kuasar UFFD']))
COLORS=['#236aa0','#d47921','#36804a','#58616a','#8a59a8','#bc4450']
INTERVALS=(0,10,25,50,100)
def read(base,interval=0):
 rows={p:json.loads((base/f'results/paced/{interval}/{p}/result.json').read_text()) for p in ORDER}
 assert all(r['batch_valid'] and not r['public_remaining'] and len(r['requests'])==256 for r in rows.values())
 return rows

def chart(series,title,y_label,english=False,height=250,x_label=None,xmax=256):
 d=Drawing(510,height);plot=LinePlot();plot.x=52;plot.y=55;plot.width=445;plot.height=height-105
 available=[(name,values,color) for name,values,color in series if values]
 if not available:
  d.add(String(52,height/2,'No measured events' if english else '无实测事件',fontName=('Helvetica' if english else 'STSong-Light'),fontSize=10));return d
 plot.data=[values for _,values,_ in available];ymax=max(1,max(y for _,values,_ in available for _,y in values)*1.08)
 plot.xValueAxis.valueMin=1;plot.xValueAxis.valueMax=max(2,xmax);plot.xValueAxis.valueStep=max(1,math.ceil(xmax/8))
 plot.yValueAxis.valueMin=0;plot.yValueAxis.valueMax=ymax;plot.yValueAxis.valueStep=ymax/5
 for axis in (plot.xValueAxis,plot.yValueAxis):axis.labels.fontName='Helvetica';axis.labels.fontSize=7
 plot.yValueAxis.labelTextFormat='%.1f';plot.yValueAxis.visibleGrid=True;plot.yValueAxis.gridStrokeColor=colors.HexColor('#e1e5e8')
 for i,(_,_,color) in enumerate(available):plot.lines[i].strokeColor=colors.HexColor(color);plot.lines[i].strokeWidth=1
 d.add(plot);d.add(String(0,height-13,title,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=11));d.add(String(0,height-29,y_label,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=8))
 d.add(String(165,34,x_label or ('Completion rank' if english else '完成的第几个请求'),fontName=('Helvetica' if english else 'STSong-Light'),fontSize=8))
 for i,(name,_,color) in enumerate(available):
  x=8+(i%3)*170;y=18-(i//3)*13;d.add(Line(x,y+2,x+15,y+2,strokeColor=colors.HexColor(color),strokeWidth=2));d.add(String(x+19,y,name,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=7))
 return d

def startup_charts(base,english=False,interval=0):
 rows=read(base,interval);series=[];gaps=[]
 for p,color in zip(ORDER,COLORS):
  r=rows[p];label=NAMES[p]+f" ({r['print']['completed']}/256)"
  series.append((label,[(i,t/1000) for i,t in enumerate(r['print']['completion_ms'],1)],color))
  gaps.append((label,[(i,t) for i,t in enumerate(r['print']['adjacent_completion_gap_ms'],2)],color))
 return [chart(series,'Print completion timeline' if english else 'Python print 完成时间线','Seconds since first scheduled request' if english else '距首个计划请求发出的实际耗时 / 秒',english),chart(gaps,'Adjacent print completion gaps' if english else '相邻两次 Python print 完成间隔','Interval / ms' if english else '时间间隔 / ms',english)]

def refill_data(base,interval=0):
 result={}
 for p in ('kuasar-fork','kuasar-mlink'):
  r=read(base,interval)[p];events=[]
  for line in (base/f'results/paced/{interval}/{p}/pool-events.jsonl').read_text().splitlines():
   try:e=json.loads(line)
   except ValueError:continue
   if p=='kuasar-fork':
    if e.get('event')!='prepared' or e.get('reason')!='refill':continue
    end=e['monotonic_ns'];duration=e['elapsed_ms'];cleanup=end>=r['cleanup_started_ns'];sort=end
   else:
    fields=e.get('fields',{})
    if fields.get('event')!='runtime_slot_prepare_execution' or not fields.get('success'):continue
    end=int(datetime.datetime.fromisoformat(e['timestamp'].replace('Z','+00:00')).timestamp()*1e9);duration=fields['total_us']/1000;cleanup=end>=r['cleanup_started_unix_ns'];sort=fields['finished_mono_us']
   events.append({'sort':sort,'duration_ms':duration,'phase':'after_cleanup' if cleanup else 'before_cleanup'})
  events.sort(key=lambda e:e['sort']);dur=[e['duration_ms'] for e in events]
  result[p]={'events':events,'during_retained_request_window':sum(e['phase']=='before_cleanup' for e in events),'after_cleanup_started':sum(e['phase']=='after_cleanup' for e in events),'median_work_ms':statistics.median(dur) if dur else None,'max_work_ms':max(dur,default=None)}
 return result

def refill_chart(base,english=False,interval=0):
 rows=refill_data(base,interval)
 series=[(NAMES[p],[(i,e['duration_ms']) for i,e in enumerate(rows[p]['events'],1)],color) for p,color in zip(('kuasar-fork','kuasar-mlink'),COLORS)]
 return chart(series,'Measured VM-slot refill work' if english else '每次 VM 补槽的实际准备耗时','Preparation work / ms' if english else '实际准备耗时 / ms',english,height=250,x_label='Refill completion rank' if english else '完成的第几个补槽',xmax=max(2,max(len(r['events']) for r in rows.values())))

def bars(rows,title,english=False,log=False,height=None):
 # rows: label, ready median, print median. Log scale starts at 1 ms.
 h=height or (len(rows)*27+65);d=Drawing(510,h);left=130;w=315
 maximum=max(v for _,a,b in rows for v in (a,b))*1.15
 upper=10**math.ceil(math.log10(maximum)) if log else maximum
 def pos(v):return left+w*(math.log10(max(1,v))/math.log10(upper) if log else v/upper)
 ticks=[10**i for i in range(int(math.log10(upper))+1)] if log else [upper*i/4 for i in range(5)]
 for v in ticks:
  x=pos(v);d.add(Line(x,27,x,h-29,strokeColor=colors.HexColor('#dddddd'),strokeWidth=.4));d.add(String(x-6,14,f'{v:.0f}',fontName='Helvetica',fontSize=7))
 d.add(String(0,h-12,title,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=11))
 for i,(label,a,b) in enumerate(rows):
  y=h-49-i*27;d.add(String(0,y+2,label,fontName=('Helvetica' if english else 'STSong-Light'),fontSize=8))
  for j,(v,color) in enumerate([(a,'#64a59a'),(b,'#3478a5')]):
   yy=y+7-j*10;d.add(Rect(left,yy,max(.4,pos(v)-left),7,fillColor=colors.HexColor(color),strokeColor=None));d.add(String(pos(v)+3,yy,f'{v:.1f}',fontName='Helvetica',fontSize=7))
 d.add(String(145,0,('Median ms (log scale)' if english else '中位数 / ms（对数刻度）') if log else ('Median ms' if english else '中位数 / ms'),fontName=('Helvetica' if english else 'STSong-Light'),fontSize=8))
 d.add(String(345,h-12,'Ready',fontName='Helvetica',fontSize=8,fillColor=colors.HexColor('#64a59a')));d.add(String(410,h-12,'print',fontName='Helvetica',fontSize=8,fillColor=colors.HexColor('#3478a5')))
 return d
