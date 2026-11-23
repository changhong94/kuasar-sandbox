import importlib.util,json,os,pathlib,tempfile,unittest,uuid,base64
from unittest.mock import patch

class ConsoleLifecycleTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();root=pathlib.Path(self.temp.name);(root/'data').mkdir();(root/'console.json').write_text(json.dumps({'api':'http://127.0.0.1:1','key':'test'}))
  spec=importlib.util.spec_from_file_location('native_console_test',pathlib.Path(__file__).with_name('server.py'));self.app=importlib.util.module_from_spec(spec)
  with patch.dict(os.environ,{'FORKLAB_ROOT':str(root)}):spec.loader.exec_module(self.app)
  self.app.init()
 def tearDown(self):self.app.POOL.shutdown();self.temp.cleanup()
 def test_reconcile_cannot_resurrect_deleted_sandbox(self):
  app=self.app;app.put('sandboxes',{'id':'s','name':'sandbox-python-00001','state':'running','runtime_id':'owned','busy':False,'renewed_at':app.time.time()})
  def backend(*args):
   app.update('sandboxes','s',state='deleted');return {'state':'running'}
  with patch.object(app,'backend',side_effect=backend),patch.object(app.time,'sleep',side_effect=InterruptedError):
   with self.assertRaises(InterruptedError):app.reconcile()
  self.assertEqual(app.get('sandboxes','s')['state'],'deleted')
 def test_deleted_template_keeps_carrier_until_child_destroyed(self):
  app=self.app;location=str(uuid.uuid4());ref='file://root.snapshot@digest:'+'1'*64+'@location:'+location
  template='e2b-snp-'+base64.urlsafe_b64encode(ref.encode()).decode().rstrip('=');directory=app.publication(template);directory.mkdir(parents=True);(directory/'owned').write_text('persistent')
  app.put('snapshots',{'id':'t','name':'snapshot-python-00001','state':'deleted','template_id':template})
  app.put('sandboxes',{'id':'s','name':'sandbox-python-00001','state':'running','snapshot_id':'t'})
  app.purge_deleted();self.assertTrue(directory.exists());app.update('sandboxes','s',state='deleted');app.purge_deleted();self.assertFalse(directory.exists());self.assertTrue(app.get('snapshots','t')['purged'])
 def test_names_retry_collisions_and_ignore_org_and_tag(self):
  app=self.app;app.put('sandboxes',{'id':'s','name':'sandbox-python-00007','state':'deleted'})
  with patch.object(app.secrets,'randbelow',side_effect=[7,8]):self.assertEqual(app.unique_display_name('sandbox','library/python:3.12-slim'),'sandbox-python-00008')
if __name__=='__main__':unittest.main()
