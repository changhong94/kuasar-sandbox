"""Restore original cache routes, then stop only this experiment's caches."""
import fcntl
import json
from pathlib import Path
import sqlite3
import subprocess as sp

B=Path('/home/hong/src/research/startup-modes-113')
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for product,afile in [('kuasar-off','/home/hong/deploy/comparison/kuasar-state/access.json'),
                          ('kuasar-uffd','/home/hong/deploy/private-pilot/uffd-state/access.json')]:
        a=json.loads(Path(afile).read_text());work=Path(a['work_dir'])
        with sqlite3.connect((work/'lib/node-ctl.db').as_uri()+'?mode=ro',uri=True) as db:
            assert db.execute('SELECT COUNT(*) FROM sandboxes').fetchone()[0]==0
        original=work/'manifest.yaml';backup=B/'backups'/(product+'-manifest.yaml')
        original.write_bytes(backup.read_bytes())
    sp.run(['systemctl','stop','bench-startup-modes-cache-off','bench-startup-modes-cache-uffd'],check=True)
    sp.run(['docker','-H','unix:///run/cube-comparison/docker.sock','rm','-f','bench-startup-modes-redis'],check=True)
    state=json.loads(Path('/home/hong/src/research/python-latest-113/data/fork/adapter-state.json').read_text())
    assert all(r.get('pool_state')=='ready' for r in state.values()), 'Assigned fork sandbox remains'
    (B/'cleanup.json').write_text(json.dumps({'original_cache_routes_restored':True,
        'experiment_cache_services_stopped':True,'experiment_redis_removed':True,
        'off_uffd_sandbox_records':0,'fork_idle_pool_slots':len(state),'fork_assigned':0},indent=2))
    print('Owned experiment caches cleaned; native locations retained; no assigned fork sandbox.')
