"""Run under exclusive measurement lock, in product network namespace, with zero sandboxes."""
import json,subprocess as sp,pathlib,sys,time
kind=sys.argv[1];assert kind in ('off','uffd')
R=pathlib.Path('/home/hong/codex-work/sevenway-fresh-181');a=json.load(open('/opt/bench108/deploy/'+kind+'/access.json'));run=pathlib.Path(a['work_dir']).name;name='k'+run[:8];ctl=a['bin']+'/connector-ctl'
def call(*args):return sp.check_output(list(args),text=True)
def status():return json.loads(call(ctl,'vswitch','status',name))
s=status();assert s['switch_netns']=='kdns-'+run and s['ports_used']==0,s
out=R/'preparation/network-capacity';out.mkdir(parents=True,exist_ok=True)
record={'before':s,'started_unix':time.time()};f=out/(kind+'-'+str(time.time_ns())+'.json');f.write_text(json.dumps(record,indent=2))
if s['ports']<320:
 planes=s['mgmt_planes'];assert len(planes)==1 and planes[0]['mgmt_netns']==''
 p=planes[0];dev=p['mgmt_dev'];assert dev=='kdm'+run
 # Preserve actual service mappings; only capacity changes. No force stop.
 args=[ctl,'vswitch','start',name,'--netns='+s['switch_netns'],'--ports=320','--mac-addr=02:00:00:00:00:01','--floating-ip-base=100.100.96.0','--mode=tap','--mgmt-extract=:'+dev+':'+','.join(p['service_routes'])]
 for v in s['mgmt_services']:
  assert v['protocols']=='tcp,udp'
  args+=['--mgmt-service='+':'.join(map(str,[v['vip'],v['vport'],v['target_ip'],v['target_port']]))]
 sp.run([ctl,'vswitch','stop',name],check=True)
 sp.run(args,check=True)
 sp.run(['ip','link','set','dev',dev,'up'],check=True)
 sp.run(['ip','addr','replace','169.254.1.0/31','dev',dev],check=True)
 sp.run(['sysctl','-q','-w','net.ipv4.conf.'+dev+'.route_localnet=1'],check=True)
record['after']=status();assert record['after']['ports']>=320 and record['after']['ports_used']==0
record['finished_unix']=time.time();f.write_text(json.dumps(record,indent=2));print(kind,'network capacity',record['after']['ports'])
