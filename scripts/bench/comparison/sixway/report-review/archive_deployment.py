from pathlib import Path
import difflib,json,subprocess
B=Path('/home/hong/src/research/report-review-113');O=B/'bench/scripts/bench/comparison/sixway/report-review/deployment';O.mkdir(exist_ok=True)
for before,after,label in [('mlink-start.sh','/home/hong/deploy/mlink-generic/start.sh','mlink-start.sh'),('off-serve.sh','/home/hong/deploy/comparison/kuasar-state/demo_e2b.sh','off-serve.sh'),('uffd-serve.sh','/home/hong/deploy/private-pilot/uffd-serve.sh','uffd-serve.sh'),('cubelet-dynamic.yaml','/usr/local/services/cubetoolbox/Cubelet/dynamicconf/conf.yaml','cubelet-dynamic.yaml')]:
 a=(B/'before'/before).read_text().splitlines(True);b=Path(after).read_text().splitlines(True)
 # Zero context avoids including unrelated service configuration/secrets.
 (O/(label+'.patch')).write_text(''.join(difflib.unified_diff(a,b,fromfile=label+'.before',tofile=label+'.after',n=0)))
(O/'cube-api-capacity.conf').write_text(Path('/etc/systemd/system/cube-sandbox-cube-api.service.d/90-benchmark-capacity.conf').read_text())
(O/'capacity.json').write_text(json.dumps({'reserves':64,'preparation_workers':8,'refill_workers':8,'mlink_total_slots':320,'mlink_max_waiters':256,'mlink_private_storage_capacity':320,'mlink_foreground_quiet_period_ms':1000,'mlink_adaptive_idle_policy':'native; initial minimum 64, observed target/ready recorded for every batch','off_network_ports':512,'uffd_network_ports':512,'off_uffd_runner_assignment_deadline_seconds':5,'cube_logical_quota':{'mcpu':640000,'mem':'640Gi','instances':320,'create_concurrency':256},'cube_api_rate_limit_per_second':4096,'physical_capacity_changed':False},indent=2))
subprocess.run(['chown','-R','hong:hong',str(O)],check=True)
print(O)
