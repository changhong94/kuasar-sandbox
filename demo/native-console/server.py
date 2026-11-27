#!/usr/bin/env python3
"""Dedicated native Kuasar console; no legacy runtime or state mutations."""
import secrets,concurrent.futures,http.server,json,os,re,sqlite3,threading,time,uuid,urllib.request,urllib.error,base64,hashlib,shutil
from pathlib import Path
from urllib.parse import urlsplit,quote
ROOT=Path(os.environ.get('FORKLAB_ROOT','/srv/forklab-native'));DATA=ROOT/'data'
SETTINGS=json.loads((ROOT/'console.json').read_text())
MAX_SANDBOXES=6
DB=DATA/'console.sqlite';LOCK=threading.RLock();POOL=concurrent.futures.ThreadPoolExecutor(4)
def db():
 c=sqlite3.connect(DB,timeout=30);c.execute('PRAGMA journal_mode=WAL');c.execute('PRAGMA synchronous=FULL');return c

def init():
 with db() as c:
  for table in ['sandboxes','snapshots']:c.execute(f'CREATE TABLE IF NOT EXISTS {table}(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, body TEXT NOT NULL)')

def rows(table):
 with db() as c:return [json.loads(x[0]) for x in c.execute(f'SELECT body FROM {table} ORDER BY rowid DESC')]

def get(table,ident):
 with db() as c:r=c.execute(f'SELECT body FROM {table} WHERE id=?',(ident,)).fetchone()
 if not r:raise ValueError('记录不存在')
 return json.loads(r[0])

def put(table,row):
 with db() as c:c.execute(f'INSERT INTO {table} VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, body=excluded.body',(row['id'],row['name'],json.dumps(row,ensure_ascii=False)))

def update(table,ident,**kw):
 with LOCK:
  row=get(table,ident);row.update(kw);put(table,row);return row


def backend(method,path,body=None):
 req=urllib.request.Request(SETTINGS['api']+path,data=None if body is None else json.dumps(body).encode(),method=method,headers={'X-API-Key':SETTINGS['key'],'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=600) as reply:return json.load(reply) if reply.status!=204 else None
 except urllib.error.HTTPError as e:
  if e.code==404:raise FileNotFoundError('原生沙箱不存在') from e
  raise RuntimeError('原生服务返回 '+str(e.code)+': '+e.read().decode()[:1000]) from e

def images():return [json.loads(p.read_text()) for p in sorted((DATA/'registry').glob('*.json'))]
def image(ident):return next(i for i in images() if i['id']==ident)
def target(ident):return '/sandboxes/'+quote(get('sandboxes',ident)['runtime_id'],safe='')
def publication(template):
 # Only locally published snapshot graphs owned by this console can be reclaimed.
 raw=template.split('-snp-',1)[1];ref=base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)).decode()
 location=ref.rsplit('@location:',1)[1]
 if not re.fullmatch(r'[0-9a-f-]{36}',location):raise ValueError('非法快照发布位置')
 digest=hashlib.sha256(location.encode()).hexdigest()
 return DATA/'publications'/digest[:2]/digest[2:4]/location

def create_worker(ident,source,kind):
 try:
  origin=image(source) if kind=='image' else get('snapshots',source)
  result=backend('POST','/sandboxes',{'templateID':origin['template_id'],'timeout':86400,'metadata':{'native-console.id':ident}})
  update('sandboxes',ident,runtime_id=result['sandboxID'])
  end=time.monotonic()+180
  while time.monotonic()<end:
   current=backend('GET',target(ident));state=current.get('state')
   if state=='running':update('sandboxes',ident,state='running',busy=False,error=None);return
   if state in ['error','dead','stopped']:raise RuntimeError('创建失败: '+str(current.get('error',state)))
   time.sleep(.1)
  raise TimeoutError('创建未能在180秒内就绪')
 except Exception as e:update('sandboxes',ident,state='failed',busy=False,error=str(e))

def action_worker(ident,action):
 try:
  if action!='destroy':raise ValueError('仅支持删除')
  if get('sandboxes',ident).get('runtime_id'):
   try:backend('DELETE',target(ident))
   except FileNotFoundError:pass
  update('sandboxes',ident,state='deleted',busy=False);purge_deleted()
 except Exception as e:update('sandboxes',ident,busy=False,error=str(e))


def purge_deleted():
 with LOCK:
  live=rows('sandboxes')
  for s in rows('snapshots'):
   if s['state']!='deleted' or s.get('purged'):continue
   if any(x.get('snapshot_id')==s['id'] and x['state']!='deleted' for x in live):continue
   if s.get('template_id'):
    directory=publication(s['template_id'])
    if directory.exists():shutil.rmtree(directory)
   update('snapshots',s['id'],purged=True)

def reconcile():
 while True:
  for row in rows('sandboxes'):
   if row['state']=='deleted' or row.get('busy') or not row.get('runtime_id'):continue
   try:
    current=backend('GET',target(row['id']));state=current['state']
    renewed=None
    if state=='running' and time.time()-row.get('renewed_at',0)>3600:
     backend('POST',target(row['id'])+'/timeout',{'timeout':86400});renewed=time.time()
    with LOCK:
     latest=get('sandboxes',row['id'])
     if latest['state']=='deleted' or latest.get('busy'):continue
     changes={'state':state if state in ['running','paused','failed'] else 'unavailable'}
     if renewed is not None:changes['renewed_at']=renewed
     update('sandboxes',row['id'],**changes)
   except FileNotFoundError:
    with LOCK:
     latest=get('sandboxes',row['id'])
     if latest['state']!='deleted' and not latest.get('busy'):update('sandboxes',row['id'],state='unavailable')
   except Exception:pass # A control-plane outage is not evidence of VM death.
  time.sleep(3)
def image_short_name(reference):
 # Drop the registry/organization and the tag or digest, not repository text.
 return reference.split('@',1)[0].rsplit('/',1)[-1].split(':',1)[0]

def unique_display_name(prefix,reference):
 # Called under LOCK together with the SQLite insert. Existing (including
 # deleted) names stay unchanged and cannot be reused by a new object.
 stem=f'{prefix}-{image_short_name(reference)}-'
 used={r['name'] for table in ['sandboxes','snapshots'] for r in rows(table)}
 if sum(n.startswith(stem) and re.fullmatch(r'[0-9]{5}',n[len(stem):]) is not None for n in used)>=100000:
  raise ValueError('此镜像的五位编号已用尽')
 while True:
  name=f'{stem}{secrets.randbelow(100000):05d}'
  if name not in used:return name

def submit(path,body):
 with LOCK:
  if path=='/api/create':
   kind=body.get('kind');source=body.get('source')
   if kind=='image':
    im=image(source)
    if im['state']!='ready':raise ValueError('镜像尚未准备完成')
   elif kind=='snapshot':
    snap=get('snapshots',source)
    if snap['state']!='ready':raise ValueError('快照尚未保存完成或已删除')
    im=image(snap['image_id'])
   else:raise ValueError('无效的创建来源')
   if len([r for r in rows('sandboxes') if r['state']!='deleted'])>=MAX_SANDBOXES:raise ValueError(f'此专属服务最多同时保留 {MAX_SANDBOXES} 个沙箱，请先销毁不用的沙箱')
   ident='sb-'+uuid.uuid4().hex[:12]
   row=dict(id=ident,name=unique_display_name('sandbox',im['name']),image_id=im['id'],image_name=im['name'],snapshot_id=source if kind=='snapshot' else None,state='creating',busy=True,created_at=time.time())
   put('sandboxes',row);POOL.submit(create_worker,ident,source,kind);return row
  if path=='/api/action':
   ident=body.get('id');action=body.get('action');row=get('sandboxes',ident)
   if row.get('busy'):raise ValueError('操作进行中，请稍候')
   allowed={'destroy':{'running','paused','failed','unavailable'}}
   if action not in allowed or row['state'] not in allowed[action]:raise ValueError('当前状态不支持此操作')
   update('sandboxes',ident,busy=True);POOL.submit(action_worker,ident,action);return {'ok':True}
  if path=='/api/delete-snapshot':
   row=get('snapshots',body.get('id'))
   if row['state'] not in ['ready','failed']:raise ValueError('正在保存的快照不能删除')
   update('snapshots',row['id'],state='deleted');purge_deleted();return {'ok':True}
  raise ValueError('未知操作')

class Handler(http.server.BaseHTTPRequestHandler):
 def reply(self,status,value,content_type='application/json; charset=utf-8'):
  b=json.dumps(value,ensure_ascii=False).encode() if isinstance(value,(dict,list)) else value
  self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/api/state':
   imgs=images();order={'python':0,'numpy':1,'pygmt':2,'pandas':3,'twisted':4};imgs.sort(key=lambda x:order[x['id']])
   public=[{k:v for k,v in x.items() if k not in ['disk','oci_config','template_id']} for x in imgs]
   return self.reply(200,dict(images=public,sandboxes=[r for r in rows('sandboxes') if r['state']!='deleted'],snapshots=[r for r in rows('snapshots') if r['state']!='deleted'],max_sandboxes=MAX_SANDBOXES,storage='local',server_time=time.time()))
  if self.path in ['/','/index.html']:return self.reply(200,(ROOT/'app/index.html').read_bytes(),'text/html; charset=utf-8')
  return self.reply(404,{'error':'Not found'})
 def do_POST(self):
  try:
   origin=self.headers.get('Origin')
   if origin and urlsplit(origin).netloc!=self.headers.get('Host'):return self.reply(403,{'error':'不允许跨站操作'})
   if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.reply(415,{'error':'JSON required'})
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=4096:raise ValueError('请求大小无效')
   body=json.loads(self.rfile.read(n));result=submit(self.path,body);self.reply(202,result)
  except (ValueError,KeyError,StopIteration,sqlite3.IntegrityError) as e:self.reply(409,{'error':str(e) or '记录不存在'})
  except Exception as e:print('request:',repr(e),flush=True);self.reply(500,{'error':str(e)})
 def log_message(self,fmt,*args):
  if self.path!='/api/state':super().log_message(fmt,*args)

if __name__=='__main__':
 init()
 for row in rows('sandboxes'):
  if row.get('busy'):update('sandboxes',row['id'],busy=False,state='unavailable',error='操作被网页重启中断，请检查原生服务状态')
 for row in rows('snapshots'):
  if row['state'] in ['capturing','saving']:update('snapshots',row['id'],state='failed',error='网页重启中断了状态确认；未删除任何快照载体')
 threading.Thread(target=reconcile,daemon=True).start()
 http.server.ThreadingHTTPServer(('0.0.0.0',18089),Handler).serve_forever()
