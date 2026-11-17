import json,os,sys,urllib.request,urllib.error
from pathlib import Path
M=Path('/opt/bench108');R=M/'results/five-rounds-108/round5';Q=M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b';sys.path.insert(0,str(Q));import vm_rpc
os.environ.update(E2B_API_KEY=(M/'deploy/fork/api-key').read_text().strip(),E2B_API_URL='http://127.0.0.1:18887',E2B_SANDBOX_URL='http://127.0.0.1:18887',NO_PROXY='*')
from e2b import Sandbox
records=json.loads((M/'data/fork/adapter-state.json').read_text());sid=min((k for k,v in records.items() if v.get('pool_state')=='ready'),key=lambda k:records[k]['pool_ready_ns'])
entry=json.loads((M/'data/fork/adapter-state.json.snapshot-preparation.json').read_text())['base']
result=vm_rpc.admin(M/'deploy/fork/admin.sock','sandbox-snapshot-stage',sandbox_id=sid,template=entry['key']);assert result['cached'] is True
paths=list((M/'data/fork/state').glob('**/image-restore-'+entry['key']+'/binding.json'))
p=next(p for p in paths if sid in p.parts)
saved=p.read_bytes();broken=json.loads(saved);broken['source']='wrong-template';p.write_text(json.dumps(broken))
try:
 headers={'X-API-Key':os.environ['E2B_API_KEY'],'Content-Type':'application/json'}
 request=urllib.request.Request('http://127.0.0.1:18887/sandboxes',data=json.dumps({'templateID':'base','timeout':30}).encode(),headers=headers)
 try:
  with urllib.request.urlopen(request,timeout=60) as response: created=json.load(response)
 except urllib.error.HTTPError as error:
  failure=error.read().decode()
  assert error.code>=500 and 'staged template/slot identity mismatch' in failure, failure
 else:
  delete=urllib.request.Request('http://127.0.0.1:18887/sandboxes/'+created['sandboxID'],headers=headers,method='DELETE')
  urllib.request.urlopen(delete,timeout=60).close()
  raise AssertionError('corrupted staged binding was accepted')
 records=json.loads((M/'data/fork/adapter-state.json').read_text());assert sid not in records or records[sid].get('pool_state')=='quarantined'
 assert not p.exists(), 'failed slot metadata was not reclaimed'
 (R/'staging-validation.json').write_text(json.dumps({'success':True,'idempotent_cache':True,'mismatched_binding_rejected':True,'failed_slot_reclaimed':True,'error':failure},indent=2))
finally:
 if p.exists():
  with p.open("wb") as f: f.write(saved);f.flush();os.fsync(f.fileno())
