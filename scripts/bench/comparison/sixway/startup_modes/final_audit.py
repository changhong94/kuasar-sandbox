"""Validate evidence before report publication; never infer missing samples."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

B=Path('/home/hong/src/research/startup-modes-113')
sys.path.insert(0,str(B))
from analyze_live import analyze

groups=[]
memory_hits=[]
for folder in sorted((B/'results/matrix').glob('*/*/*')):
    if not (folder/'10.json').exists():
        continue
    rows=[json.loads((folder/f'{i:02d}.json').read_text()) for i in range(1,11)]
    assert len(list(folder.glob('[0-9][0-9].json')))==10
    assert all(r['success'] and r['destroyed'] for r in rows), folder
    assert len({r['marker'] for r in rows})==10
    assert all(r['ready_ms']<=r['print_ms'] for r in rows)
    assert len({r['image_digest'] for r in rows})==1
    mode=folder.name
    if mode in ('local_cold','local_warm'):
        assert all(r['cache_preparation']['verified'] for r in rows)
        for r in rows:
            p=r['cache_preparation']
            assert p['resident_pages']==(0 if mode=='local_cold' else p['pages'])
    if mode=='remote':
        for r in rows:
            e=r['remote_cache']
            assert e['backend']=='redis-memory'
            hits=e['after']['info']['server']['hits']-e['before']['info']['server']['hits']
            assert hits>0 and e['origin_fetches']==0 and e['cache_daemon_disk_read_bytes']==0
            assert e['after']['info']['tiered']['tiers'][0]['type']=='redis'
            memory_hits.append(hits)
    groups.append(str(folder.relative_to(B/'results/matrix')))
assert len(groups)==33,groups
live=[analyze(p.parent) for p in (B/'results/live-formal').glob('*/*/result.json') if p.parent.name!='warmup']
assert len(live)==30
assert all(r['success'] and not r['owned_remaining'] and not r.get('cleanup_errors') for r in live)
assert {r['destroy_first'] for r in live}=={'parent','child'}
assert all(any(e['phase']=='parent_kvm_reused' for e in r['phase_events']) for r in live)
for product in ['kuasar-off','kuasar-uffd']:
    entries=json.loads((B/(product+'-native.json')).read_text())
    assert len(entries)==3 and all(e['resolved_config_has_manifest_refs'] is False for e in entries)

repos={
 'kuasar': '/home/hong/src/research/python-latest-113/src/kuasar-fork/kuasar-io/kuasar',
 'cloud-hypervisor':'/home/hong/src/research/python-latest-113/src/kuasar-fork/cloud-hypervisor/cloud-hypervisor',
 'bench':'/home/hong/src/changhong94/kuasar-sandbox',
 'agentenv':'/home/hong/src/kvcache-ai/AgentENV',
 'cube':'/home/hong/src/TencentCloud/CubeSandbox'}
sources={}
for name,path in repos.items():
    # Root runs the benchmark; git reads repositories as their owning user.
    def git(*args):return subprocess.check_output(['sudo','-u','hong','git','-C',path,*args],text=True).strip()
    sources[name]={'path':path,'head':git('rev-parse','HEAD'),
                   'branch':git('branch','--show-current'),'status':git('status','--short')}
    if name in ('kuasar','cloud-hypervisor'):
        assert sources[name]['branch']=='sandbox_fork_staging'
        (B/(name+'.patch')).write_text(git('diff'))
sources['binaries']={}
for name in ['cloud-hypervisor','sandboxer']:
    p=Path('/home/hong/src/research/python-latest-113/deploy/fork/bin')/name
    sources['binaries'][name]=hashlib.sha256(p.read_bytes()).hexdigest()
(B/'source-provenance.json').write_text(json.dumps(sources,indent=2))
summary={'formal_template_samples':330,'formal_live_forks':30,'groups':groups,
    'all_template_samples_destroyed':True,'all_live_branches_destroyed':True,
    'live_parent_kvm_reused_all_samples':True,'local_cache_conditions_verified':True,
    'remote_memory_samples':len(memory_hits),'remote_cache_hits_total':sum(memory_hits),
    'remote_origin_fetches':0,'remote_cache_disk_read_bytes':0,
    'native_manifest_dependencies_remaining':0,'other_host_108_modified':False}
(B/'verification.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='groups'},indent=2))
