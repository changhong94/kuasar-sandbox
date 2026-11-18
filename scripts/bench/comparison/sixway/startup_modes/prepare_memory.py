"""Independent memory-only cache replica; persistent origin is unchanged."""
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess as sp
import time

B = Path('/home/hong/src/research/startup-modes-113')
IMAGE = 'sha256:8cde46b4aa591f2e94cd60c2d2f1ca34d86cb0908908d6a2b074b0f770317d10'
CACHE = '/home/hong/src/private/kuasar-uffd/kuasar-sandbox/bin/x86_64/cache-ctl'
memory = B/'memory'

def redis_info(path):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(5)
        sock.connect(str(path))
        sock.sendall(b'*1\r\n$4\r\nINFO\r\n')
        stream=sock.makefile('rb')
        size=stream.readline();assert size.startswith(b'$'), size
        value=stream.read(int(size[1:-2])).decode()
    return dict(line.split(':',1) for line in value.splitlines() if ':' in line and not line.startswith('#'))


with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    start=time.monotonic_ns()
    memory.mkdir(exist_ok=True)
    (memory/'redis').mkdir(exist_ok=True)
    docker=['docker','-H','unix:///run/cube-comparison/docker.sock']
    existing=sp.run(docker+['inspect','--format','{{.Image}}','bench-startup-modes-redis'],capture_output=True,text=True)
    if existing.returncode == 0:
        assert existing.stdout.strip() == IMAGE
    else:
        sp.run(docker+['run','-d','--name','bench-startup-modes-redis','--network','none',
            '--memory','2g','--cpus','2','-v',str(memory/'redis')+':/data:z',IMAGE,
            'redis-server','--port','0','--unixsocket','/data/redis.sock','--unixsocketperm','600',
            '--save','','--appendonly','no','--maxmemory','1536mb','--maxmemory-policy','noeviction'],check=True)
    redis_socket=memory/'redis/redis.sock'
    for _ in range(100):
        try:
            info=redis_info(redis_socket)
            break
        except (OSError, AssertionError):
            time.sleep(.1)
    else:
        raise TimeoutError('Redis readiness')
    assert info['aof_enabled']=='0'
    settings={};costs=[]
    for product,afile in [('kuasar-off','/home/hong/deploy/comparison/kuasar-state/access.json'),
                          ('kuasar-uffd','/home/hong/deploy/private-pilot/uffd-state/access.json')]:
        a=json.loads(Path(afile).read_text());work=Path(a['work_dir']);suffix=product.rsplit('-',1)[-1]
        original=work/'manifest.yaml'
        backup=B/'backups'/(product+'-manifest.yaml')
        if not backup.exists():
            backup.write_bytes(original.read_bytes());backup.chmod(0o600)
        old_cache=re.search(r"cache:.*endpoint:\s*['\"]?([^'\" },]+)",backup.read_text())[1]
        origin=re.search(r"store:.*endpoint:\s*['\"]?([^'\" },]+)",backup.read_text())[1]
        data_socket=memory/(suffix+'-cache.sock');health=memory/(suffix+'-health.sock')
        config=memory/(suffix+'-cache.yaml')
        config.write_text(f'''mode: tiered
listen: unix://{data_socket}
health_listen: unix://{health}
rpc_timeout: 5s
tiers:
  - type: redis
    redis:
      endpoint: unix://{redis_socket}
      get_pool: 32
      set_pool: 8
      timeout: 5s
origin:
  type: store
  store: {{ endpoint: '{origin}', pool: 4, timeout: 5s }}
  max_inflight: 32
''')
        sp.run([CACHE,'config','show','--config',str(config)],check=True,stdout=sp.DEVNULL)
        service='bench-startup-modes-cache-'+suffix
        if sp.run(['systemctl','is-active','--quiet',service]).returncode:
            sp.run(['systemctl','reset-failed',service],stdout=sp.DEVNULL,stderr=sp.DEVNULL)
            sp.run(['systemd-run','--unit',service,'--property=MemoryMax=1G',
                    '/bin/bash','-c','exec "$1" serve --config "$2"','bash',CACHE,str(config)],check=True)
        for _ in range(100):
            probe=sp.run([CACHE,'ping','--endpoint','unix://'+str(health)],stdout=sp.DEVNULL,stderr=sp.DEVNULL)
            if probe.returncode==0:break
            time.sleep(.1)
        else:raise TimeoutError('Memory cache health')
        original.write_text(backup.read_text().replace(old_cache,'unix://'+str(data_socket)))
        settings[product]={'endpoint':'unix://'+str(health),'config':str(config),
            'redis_socket':str(redis_socket),'backend':'redis-memory','service':service,
            'origin':origin,'persistent_origin_unchanged':True}
        with sqlite3.connect((work/'lib/node-ctl.db').as_uri()+'?mode=ro',uri=True) as db:
            assert db.execute('SELECT COUNT(*) FROM sandboxes').fetchone()[0]==0
            records=db.execute('SELECT manifest_key_enc FROM manifest_keys').fetchall()
        assert len(records)==1
        root=re.search(r'^\s*encryption_key:\s*["\']?([0-9a-f:]+)',(work/'conductor.yaml').read_text(),re.M)[1]
        key=sp.check_output([str(B/'unseal')],input=json.dumps({'Root':root,'Sealed':records[0][0]}),text=True)
        env={**os.environ,'MANIFEST_KEY':key};binary=Path(a['bin'])
        def refs(value):
            if isinstance(value,dict):return set().union(*(refs(v) for v in value.values())) if value else set()
            if isinstance(value,list):return set().union(*(refs(v) for v in value)) if value else set()
            return {value} if isinstance(value,str) and value.startswith('manifest://') else set()
        for row in json.loads((B/(product+'-native.json')).read_text()):
            begin=time.monotonic_ns();source=row['source']
            meta=json.loads(sp.check_output([str(binary/'sandbox-ctl'),'info','--json',
                '--manifest-config',str(original),source],text=True,env=env))
            dependencies=refs(meta)|{source}
            for ref in sorted(dependencies):
                with sp.Popen([str(binary/'manifest-ctl'),'load','--manifest-config',str(original),
                    '--no-progress','--output','-',ref],env=env,stdout=sp.PIPE) as process:
                    while process.stdout.read(1024*1024):
                        pass
                    assert process.wait() == 0, 'Manifest prefill failed'
            costs.append({'product':product,'language':row['language'],'refs':len(dependencies),
                          'prefill_ms':(time.monotonic_ns()-begin)/1e6})
    (B/'remote-cache.json').write_text(json.dumps(settings,indent=2))
    info=redis_info(redis_socket)
    (B/'memory-preparation.json').write_text(json.dumps({'backend':'Redis / Unix socket',
        'image':IMAGE,'elapsed_ms':(time.monotonic_ns()-start)/1e6,
        'used_memory_bytes':int(info['used_memory']),'maxmemory_bytes':int(info['maxmemory']),
        'aof_enabled':info['aof_enabled'],'evicted_keys':int(info['evicted_keys']),
        'costs':costs,'redis_info':info},indent=2))
    print('MEMORY CACHE READY',info['used_memory'],flush=True)
