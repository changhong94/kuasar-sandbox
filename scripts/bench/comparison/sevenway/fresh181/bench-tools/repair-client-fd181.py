import pathlib,json,fcntl,subprocess,time,resource
r=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181')
with (r/'measurement.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 p=r/'measurements/burst/kuasar-mlink/0';d=json.loads((p/'result.json').read_text())
 assert d['successes']==250 and not d['owned_remaining']
 errors=[s['error'] for s in d['samples'] if not s.get('success')]
 assert len(errors)==6 and all('Too many open files' in e for e in errors)
 assert len(d['isolation_verified_ids'])==250
 archive=r/'failures'/('memlink-client-fd-'+str(time.time_ns()));p.rename(archive)
 meta={'reason':'client subprocess pipes exhausted soft FD limit, not server failure','rlimit_nofile':resource.getrlimit(resource.RLIMIT_NOFILE),'original_result':str(archive)}
 (r/'memlink-client-fd-repair.json').write_text(json.dumps(meta,indent=2))
 c=json.loads((r/'tools/config.json').read_text())['kuasar-mlink']
 cmd=['nsenter','--net=/run/netns/'+c['netns'],'/opt/bench108/venv/bin/python',str(r/'tools/burst_worker181.py'),'kuasar-mlink','0']
 with (r/'memlink-client-fd-repair.log').open('w') as log:z=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 meta.update(exit=z.returncode,finished_unix=time.time());(r/'memlink-client-fd-repair.json').write_text(json.dumps(meta,indent=2))
