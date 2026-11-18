"""Aggregate only freshly rerun resource cases from this revision."""
from pathlib import Path
import hashlib
import json
import statistics as st

H=Path('/home/hong/src/research/report-revision-113/results')
B=H.parent
inputs={}
def read(path):
    data=path.read_bytes();inputs[str(path.relative_to(H))]=hashlib.sha256(data).hexdigest()
    return json.loads(data)
completion=read(H/'complete.json')
assert completion['timing_records']==30 and completion['storage_records']==36 and completion['memory_cases']==24
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
data={'batch':'report-revision-113 / fresh resource rerun','source':str(H),
      'python_only':True,'resource_pool_capacity':64,
      'fork_business_filesystem':'persistent qcow2 ext4 overlay',
      'products':result,'completion':completion,'input_sha256':inputs,
      'definitions':{'short_ms':'median of five per-round medians, eight true commands per round',
          'cpu_ms':'guest elapsed time hashing 256 MiB; precomputed input buffer excluded',
          'io_ms':'guest elapsed time generating, hashing, writing and fsyncing 32 MiB',
          'throughput':'8 complete create/print/hash/delete tasks with concurrency 2; median of 5 batches',
          'memory':'product-owned process PSS, including dedicated sidecars; shared pages charged proportionally; excludes unmapped page cache and most kernel memory',
          'storage':'within-filesystem union of FIEMAP physical extents, then sum filesystems; same shared extent counted once within a product; delta vs before creating the two sandboxes'}}
(B/'resource-suite.json').write_text(json.dumps(data,indent=2))
print('Verified fresh resource batch:',len(inputs),'input files.')
