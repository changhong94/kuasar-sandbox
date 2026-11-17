import importlib.util,json,os,tempfile,pathlib
R=pathlib.Path('/opt/bench108/results/tail-opt-108');os.environ['E2B_SQLITE_JOURNAL']='WAL'
paths={'before':R/'before/durable_state.py','after':pathlib.Path('/opt/bench108/src/kuasar-fork/kuasar-io/kuasar/integrations/e2b/durable_state.py')};result={}
for name,path in paths.items():
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 with tempfile.TemporaryDirectory(prefix='tail-wal-',dir='/opt/bench108/data') as root:
  p=pathlib.Path(root)/'state';s=m.DurableState(p)
  records={str(i):{'payload':'x'*650,'lease':0,'status':'ready'} for i in range(64)};s.save(records)
  # Disable checkpoint only in this disposable experiment to count WAL bytes;
  # production checkpoint settings are unchanged.
  s.db.execute('PRAGMA wal_autocheckpoint=0');s.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
  for i in range(10):
   records[str(i)].update(lease=1,status='binding',snapshot_template='image-'+'a'*32)
   s.save(records)
  result[name]={'updates':10,'wal_bytes':pathlib.Path(str(p)+'.sqlite3-wal').stat().st_size,'synchronous':s.db.execute('PRAGMA synchronous').fetchone()[0]}
  assert s.load()==records;s.close()
result['reduction_percent']=(1-result['after']['wal_bytes']/result['before']['wal_bytes'])*100
(R/'wal-amplification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
