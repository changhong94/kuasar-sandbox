"""Read the previously validated full resource batch; do not relabel as new."""
from pathlib import Path
import hashlib
import json
import statistics as st

H=Path('/home/hong/src/research/sixway-aligned-20261117/results')
B=Path('/home/hong/src/research/startup-modes-113')
inputs={}
def read(path):
    data=path.read_bytes();inputs[str(path.relative_to(H))]=hashlib.sha256(data).hexdigest()
    return json.loads(data)
audit=read(H/'final-audit.json')
assert audit['complete'] and audit['all_workloads_verified'] and audit['all_owned_cleaned']
timing=[read(p) for p in (H/'timing').glob('[1-5]-*.json')]
assert len(timing)==30
storage=[read(p) for p in (H/'timing/storage').glob('[1-3]-*.json')]
assert len(storage)==36 and all(d['success'] and not d['remaining'] for d in storage)
result={}
for name in ['kuasar-fork','kuasar-mlink','agentenv','cube','kuasar-off','kuasar-uffd']:
    rows=[d for d in timing if d['product']==name]
    assert len(rows)==5 and all(d['success'] and not d['owned_remaining'] and all(x['success'] for x in d['pressure']) for d in rows)
    r=dict(print_ms=st.median(d['ready_ms'] for d in rows),
        print_max_ms=max(d['ready_ms'] for d in rows),
        short_ms=st.median(st.median(d['short_ms']) for d in rows),
        cpu_ms=st.median(d['cpu'][1] for d in rows),
        io_ms=st.median(d['io'][1] for d in rows),
        throughput=st.median(d['throughput'] for d in rows))
    for key in ['pause_ms','resume_ms']:
        r[key]=st.median(d[key] for d in rows) if all(d[key] is not None for d in rows) else None
    growth=read(H/'growth'/f'{name}.json')
    assert growth.get('verified')==50 and not growth['owned'] and not growth.get('error')
    levels={}
    for sample in growth['samples']:
        levels[sample['instances']]=st.median(x['pss_mib'] for x in sample['resources'])
    arrays={}
    for mode in ['default','100','random']:
        a=read(H/'arrays'/f'{name}-{mode}.json')
        assert a['success'] and not a['owned'] and not a.get('error')
        arrays[mode]=a[mode]-a['python']
    r['memory']={'levels':levels,'increment_per_instance':(levels[50]-levels[0])/50,'arrays':arrays}
    r['storage']={}
    for different in [False,True]:
        cases=[d for d in storage if d['product']==name and bool(d['different'])==different]
        assert len(cases)==3
        values={}
        for stage in ['live2','paused2']:
            ext=[];pss=[]
            for d in cases:
                before=d['stages']['before'];after=d['stages'][stage]
                if after.get('supported') is False:continue
                if before['extent']['valid'] and after['extent']['valid']:
                    ext.append((after['extent']['unique_extent_bytes']-before['extent']['unique_extent_bytes'])/2**20)
                pss.append(after['pss_mib']-before['pss_mib'])
            values[stage]={'extent_mib':st.median(ext) if ext else None,'pss_mib':st.median(pss) if pss else None}
        r['storage']['different' if different else 'same']=values
    result[name]=r
data={'batch':'A / sixway-aligned-20261117','source':str(H),
      'not_remeasured_in_startup_modes_batch':True,'python_only':True,'resource_pool_capacity':64,
      'fork_business_filesystem':'guest RAM overlay in this older resource batch',
      'products':result,'audit':audit,'input_sha256':inputs,
      'preparation':read(H/'resource-profile-preparation.json'),
      'readiness':read(H/'resource-readiness.json')}
(B/'resource-suite.json').write_text(json.dumps(data,indent=2))
print('Verified prior resource batch:',len(inputs),'input files; no new resource measurements claimed.')
