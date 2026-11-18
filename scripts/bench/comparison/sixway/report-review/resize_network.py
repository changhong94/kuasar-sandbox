from pathlib import Path
import fcntl,json,subprocess,sqlite3,time
B=Path('/home/hong/src/research/report-review-113')
def output(args):return subprocess.check_output(args,text=True)
with open('/run/skyrl-threeway-benchmark.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 results={}
 for product,ns,access,switch,script in [('off','bench113','/home/hong/deploy/comparison/kuasar-state/access.json','k72667ef5','/home/hong/deploy/comparison/kuasar-state/demo_e2b.sh'),('uffd','bench113-u','/home/hong/deploy/private-pilot/uffd-state/access.json','kuffd113a','/home/hong/deploy/private-pilot/uffd-serve.sh')]:
  a=json.loads(Path(access).read_text());w=Path(a['work_dir'])
  with sqlite3.connect((w/'lib/node-ctl.db').as_uri()+'?mode=ro',uri=True) as db:assert db.execute('select count(*) from sandboxes').fetchone()[0]==0
  prefix=['nsenter','--net=/run/netns/'+ns];ctl=prefix+[a['bin']+'/connector-ctl','vswitch']
  status=json.loads(output(ctl+['status',switch]));cfg=json.loads(output(ctl+['show','config',switch]));assert status['ports_used']==0 and status['ports']==64
  assert len(status['mgmt_planes'])==1
  mgmt=status['mgmt_planes'][0];dev=mgmt['mgmt_dev'];assert mgmt['mgmt_netns']==''
  addr=json.loads(output(prefix+['ip','-j','addr','show','dev',dev]));routes=json.loads(output(prefix+['ip','-j','route','show','dev',dev]))
  sysctls={k:output(prefix+['sysctl','-n','net.ipv4.conf.'+dev+'.'+k]).strip() for k in ('forwarding','route_localnet','rp_filter','accept_local')}
  record={'before':status,'config':cfg,'address':addr,'routes':routes,'sysctls':sysctls};(B/'before'/('network-'+product+'.json')).write_text(json.dumps(record,indent=2))
  p=Path(script);s=p.read_text();assert '--ports=64' in s;(B/'before'/(product+'-serve.sh')).write_text(s);p.write_text(s.replace('--ports=64','--ports=512'))
  subprocess.run(ctl+['stop',switch,'--force'],check=True)
  args=ctl+['start',switch,'--netns='+status['switch_netns'],'--ports=512','--mac-addr='+cfg['switch_mac'],'--floating-ip-base='+cfg['floating_ip_base'],'--mode=tap','--mgmt-extract=:'+dev+':'+','.join(mgmt['service_routes'])]
  for svc in status['mgmt_services']:args+=['--mgmt-service='+':'.join(str(svc[k]) for k in ('vip','vport','target_ip','target_port'))]
  subprocess.run(args,check=True)
  subprocess.run(prefix+['ip','link','set',dev,'mtu',str(addr[0]['mtu']),'up'],check=True)
  for x in addr[0]['addr_info']:
   if x['family']=='inet':subprocess.run(prefix+['ip','addr','replace',x['local']+'/'+str(x['prefixlen']),'dev',dev],check=True)
  for k,v in sysctls.items():subprocess.run(prefix+['sysctl','-q','-w','net.ipv4.conf.'+dev+'.'+k+'='+v],check=True)
  for r in routes:
   if r.get('protocol')=='kernel':continue
   args=prefix+['ip','route','replace',r.get('dst','default')]
   if r.get('gateway'):args+=['via',r['gateway']]
   args+=['dev',dev]
   if r.get('metric') is not None:args+=['metric',str(r['metric'])]
   subprocess.run(args,check=True)
  after=json.loads(output(ctl+['status',switch]));assert after['ports']==512 and after['ports_used']==0
  results[product]={'before_ports':64,'after':after,'time':time.time()};(B/'network-capacity.json').write_text(json.dumps(results,indent=2));print(product,'512 network ports ready',flush=True)
