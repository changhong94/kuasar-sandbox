from pathlib import Path
import subprocess,xml.etree.ElementTree as ET,json
b=Path(__file__).parent/'evidence/report';pdf=b/'sandbox-sixway-zh-en.pdf'
subprocess.run(['pdftotext','-layout',str(pdf),str(b/'report.txt')],check=True)
subprocess.run(['pdftotext','-bbox-layout',str(pdf),str(b/'bbox.html')],check=True)
text=(b/'report.txt').read_text();pages=[p for p in text.split('\f') if p.strip()]
for i,p in enumerate(pages,1):
 lines=[v.strip() for v in p.splitlines() if v.strip()]
 print(i,len(lines),lines[0], 'LAST:',lines[-2][:90])
assert '结果摘要' in pages[0]
for phrase in ['历史附录','本轮未重测','墙钟时间','准备与发布成本','启动批次时间','未经批准不合入']:
 assert phrase not in text,phrase
root=ET.parse(b/'bbox.html').getroot();errors=[]
for i,page in enumerate(root.findall('.//{*}page'),1):
 w,h=float(page.attrib['width']),float(page.attrib['height'])
 for word in page.findall('.//{*}word'):
  a=word.attrib
  if float(a['xMin'])<0 or float(a['yMin'])<0 or float(a['xMax'])>w+1 or float(a['yMax'])>h+1:errors.append((i,word.text,a))
assert not errors,errors
(b/'pdf-audit.json').write_text(json.dumps({'pages':len(pages),'page_bounds_ok':True,'removed_sections_absent':True,'english_summary_page':next(i for i,p in enumerate(pages,1) if p.strip().startswith('Results summary:'))},indent=2))
print('Basic PDF text and bounds audit passed.')
