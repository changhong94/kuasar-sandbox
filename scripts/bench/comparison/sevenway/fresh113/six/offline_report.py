from pathlib import Path
import hashlib, json, sys, statistics as st, collections, datetime, re

base=Path(__file__).resolve().parent
old=base.parent/'report-review-113'; attempts=base/'attempts'; out=base/'offline-report'; out.mkdir(exist_ok=True)
files={}
def raw(path):
    path=path.resolve(); data=path.read_bytes(); files[str(path)]=hashlib.sha256(data).hexdigest(); return data
def read(path): return json.loads(raw(path))
def one(pattern):
    matches=list(attempts.glob(pattern)); assert len(matches)==1,pattern; return matches[0]
source=raw(base/'report.py').decode(); exec(source[:source.index('B=Path')]); exec(source[source.index('order='):source.index('def summary_page')]); exec(source[source.index('def footer'):source.index("ReportDoc(str")]); import paced_charts as charts
raw(base/'paced_charts.py'); med=st.median; fork,mlink=order[:2]; cells={}; snaps={}; bursts={}; image=read(old/'image-verification.json'); resource=read(old/'resource-suite.json'); resources=resource['products'].copy(); del resources[fork]; dates={}; ids={}
for lang in langs:
    ident=read(one('fork-identity-*/'+lang+'.json')); assert ident['success'] and ident['destroyed'] and ident['no_interpreter_running']; ids[lang]=ident
    for product in order:
        if product!=fork:
            probe=next(row for row in image['rows'] if (row['language'],row['product'])==(lang,product)); assert all(probe[key]==ident[key] for key in ['image_digest','interpreter_sha256'])
        dirs=list(attempts.glob('fork-startup-*/*/01.json')) if product==fork else list((old/'results/matrix'/lang/product).glob('*/01.json'))
        for path in dirs:
            first=read(path)
            if first['language']!=lang: continue
            folder=path.parent; samples=[read(folder/f'{idx:02}.json') for idx in range(1,51)]; warm=read(folder/'warmup.json'); assert warm['warmup'] and warm['success']; assert all(not row['warmup'] and row['success'] and row['destroyed'] and row['marker'] in row['received_marker'] and row['image_digest']==ident['image_digest'] for row in samples); cells[product,lang,first['mode']]=samples
            ds=dates.setdefault(product,set()); ds.update(datetime.fromtimestamp(row['start_unix_ns']/1e9,timezone.utc).date().isoformat() for row in samples)
for product in order:
    folder=one('fork-snapshot-*/samples') if product==fork else old/'results/persistence-python'/product
    snaps[product]=[read(folder/f'{idx:02}.json') for idx in range(1,11)]; assert read(folder/'warmup.json')['warmup']; assert all(row['success'] and row['destroyed'] and row['file_state_verified'] and row['process_state_verified'] for row in snaps[product]);
    for interval in charts.INTERVALS:
        folder=one(f'fork-paced-TR*/results/{interval}/{product}') if product==fork else old/f'results/paced/{interval}/{product}'; rec=read(folder/'result.json'); assert rec['batch_valid'] and len(rec['requests'])==256 and not rec['owned_remaining']; bursts[product,interval]=rec
        link=out/f'results/paced/{interval}/{product}';link.parent.mkdir(parents=True,exist_ok=True); link.symlink_to(folder) if not link.exists() else None
        if product in (fork,mlink): raw(folder/'pool-events.jsonl')
rounds=[read(path) for path in attempts.glob('fork-resource-*/result.json')]; rounds=[row for row in rounds if row['success'] and not row['owned_remaining']]; assert sorted(int(row['round']) for row in rounds)==list(range(1,6)); growth=read(one('fork-memory-growth*/kuasar-fork.json')); assert growth['verified']==50 and not growth['owned']; levels={str(row['instances']):med(v['pss_mib'] for v in row['resources']) for row in growth['samples']}; arrays={}
for mode in ['default','100','random']:
    row=read(one(f'fork-memory-{mode}*/kuasar-fork-{mode}.json')); assert row['success'] and not row['owned']; arrays[mode]=row[mode]-row['python']
resources[fork]=dict(short_ms=med(med(row['short_ms']) for row in rounds),cpu_ms=med(row['cpu'][1] for row in rounds),io_ms=med(row['io'][1] for row in rounds),throughput=med(row['throughput'] for row in rounds),memory=dict(levels=levels,arrays=arrays),storage={kind:{stage:{'extent_mib':None} for stage in ['live2','paused2']} for kind in ['different','same']})
storage_batches={}
for batch,root in [('optimized108',base/'storage-supplement'),('previous113',base.parent/'storage-incremental-113/local/results/storage')]:
    storage_batches[batch]={}
    for diff,kind in [(0,'same'),(1,'different')]:
        rs=[read(root/f'{i}-{diff}-kuasar-fork.json') for i in range(1,4)]
        assert all(r['success'] and not r['remaining'] and r['different']==diff for r in rs)
        storage_batches[batch][kind]={}
        for stage in ['live2','paused2']:
            values=[(r['stages'][stage]['extent']['unique_extent_bytes']-r['stages']['before']['extent']['unique_extent_bytes'])/2**20 for r in rs]
            storage_batches[batch][kind][stage]={'extent_mib':med(values),'samples_mib':values,'maximum_mib':max(values),'n':3}
resources[fork]['storage']=storage_batches['optimized108']
raw(base/'storage-supplement/retained-version.json'); raw(base.parent/'storage-incremental-113/source-manifest.json')
for name,digest in resource['input_sha256'].items():
    path=Path(resource['source'])/name; assert hashlib.sha256(raw(path)).hexdigest()==digest
livepath=one('live-parent-*/samples/analyzed.json'); live=read(livepath)['python']; lr=[read(livepath.parent/f'python/{idx:02}/result.json') for idx in range(1,51)]; assert all(r['independent_destroy'] and r['independent_files'] and r['inherited_process_continues'] and not r['owned_remaining'] for r in lr) and len(set(r['destroy_first'] for r in lr))==2
fd=[json.loads(line) for line in raw(one('fork-fd-*/samples.jsonl')).splitlines()]; fd=[r for r in fd if r.get('unit','').endswith('fork-vmm.service')]; raw(base/'cleanup-audit.json'); pool=read(old/'results/pool-analysis.json'); raw(old/'runtime-binary-manifest.json'); raw(base/'provenance/harness.json')
local113=[read(base.parent/f'storage-incremental-113/local/results/snapshots/kuasar-fork/{i:02d}.json') for i in range(1,11)]
local108=[read(base/f'local108-snapshots/{i:02d}.json') for i in range(1,11)]
for cohort in [local113,local108]:
    assert len(cohort)==10 and all(r['success'] and r['destroyed'] and r['process_state_verified'] and r['file_state_verified'] for r in cohort)
    assert {r['image_digest'] for r in cohort}=={ids['python']['image_digest']}
raw(base.parent/'storage-incremental-113/local/deployment-public.json')
raw(base/'deployment/fork/config.toml')
raw(base/'retirement/units-before-stop.txt')
config_source=raw(base.parent/'sandbox_fork/kuasar-io/kuasar/vmm/sandbox/src/config.rs').decode()
assert '#[default]\n    Remote' in config_source and 'checkpoint_mode' not in (base/'deployment/fork/config.toml').read_text()
event_rows=[json.loads(l) for l in raw(base/'offline-evidence/adapter-state.json.pool-events.jsonl').splitlines()]
valid_epoch=json.loads(raw(one('fork-paced-TR*/results/0/kuasar-fork/pool-events.jsonl')).splitlines()[0])['epoch']
initial=[r for r in event_rows if r.get('epoch')==valid_epoch and r.get('reason')=='startup']
prepared=[r for r in initial if r['event']=='prepared'];started=[r for r in initial if r['event']=='prepare_started']
assert len(prepared)==len(started)==64 and len({r['sid'] for r in prepared})==64
pool_finish=max(r['monotonic_ns'] for r in prepared);pool_begin=min(r['monotonic_ns'] for r in started)
fork_pool={'first_to_full_ms':(pool_finish-pool_begin)/1e6,'single_slot_median_ms':med(r['elapsed_ms'] for r in prepared),'single_slot_max_ms':max(r['elapsed_ms'] for r in prepared),'n':64,'epoch':valid_epoch}
previous_fork_slot=read(old/'results/pool-memory.json')[fork]['summary']
def sample(product,lang,key): return med(row[key] for row in cells[product,lang,reference(product)])
def provenance(): text('fork 为新测；其余五方为此前独立批次。图表并非同时运行。','Fork is newly measured; the five comparators come from earlier, separate batches. Charts do not represent simultaneous runs.','small')
def signature(row):return tuple(row[key] for key in ['timer_start','timer_end','interpreter_code','image_digest'])
for lang in langs:
    signature_set={signature(row) for (prod,language,mode),items in cells.items() if language==lang for row in items}; assert len(signature_set)==1
assert all(len([1 for prod,language,mode in cells if prod==fork and language==lang])==3 for lang in langs)
failures=read(old/'failure-analysis.json'); slot=read(old/'results/pool-memory.json')[mlink]['summary']; raw(base/'offline_report.py')
for path in [base/'cloud-hypervisor.json',base/'vmm-sandboxer.json',base/'ownership.json',old/'snapshot-batch.json',old/'source-provenance-startup.json',old/'results/matrix/complete.json',one('fork-snapshot-*/run.py'),one('fork-identity-*/paced-audit.json')]:raw(path)
for interval in charts.INTERVALS:
    record=bursts[fork,interval];assert len(set(record['retained_alive_before_cleanup']))==256 and record['print']['completed']==256 and not record['failed_requests'] and record['cleanup_quiescence_verified']
for row in lr:assert row['success']
for r in fd:assert (r['pid'],r['birth'])==(fd[0]['pid'],fd[0]['birth'])
state={'scope':'Offline reporting only. Not full benchmark validation.','images':{lang:{key:probe[key] for key in ['image_digest','interpreter_sha256','memory_kib','vcpus']} for lang,probe in ids.items()},'historical_images':[{k:r[k] for k in ['product','language','image_digest','interpreter_sha256','memory_kib','vcpus']} for r in image['rows'] if r['product']!=fork],'startup':[{ 'product':p,'language':lang,'mode':mode,'date_utc':sorted(dates[p]),'n':len(rows),'excluded_warmups':1,'timer_start':rows[0]['timer_start'],'timer_end':rows[0]['timer_end'],'command_example':rows[0]['command']} for (p,lang,mode),rows in cells.items()],'resource_definitions':resource['definitions'],'pool_recomputed':fork_pool,'pool_pss_prior113':previous_fork_slot,'persistence_mode':{'current113':'remote (default config)','retained113':'local','optimized108':'local; separate host'},'snapshot_n':10,'resource_rounds':5,'live_parent_n':50,'retained_requests_per_fork_interval':256,'unavailable':['Fresh paused physical PSS deltas','Current-batch per-slot PSS (prior113 dedicated measurement provided instead)','Pre-create unique physical disk footprint matched to local target files','Completed long-duration FD release proof'],'disk_supplement':{'latest_optimized_host':'108','previous_host':'113','prepared_slots_108':2,'prepared_slots_comparators_113':64,'batches':storage_batches,'method':'Per-pair FIEMAP unique physical extent union delta against pre-create baseline; n=3 pairs, 32 MiB fsynced per guest; local native persistence. Cross-host ratios suppressed.'},'excluded':'Failed pre-repair fork resource round and EMFILE paced attempt; historical fork excluded except explicitly labelled local persistence, disk and slot-PSS references.'};(out/'methods.json').write_text(json.dumps(state,indent=2))
for english in (False,True):
    page('结果摘要：fork 与 mlink','Results summary: fork versus mlink'); provenance(); text(tr('启动样本日期（UTC）：','Startup sample dates (UTC): ')+', '.join(names[p]+': '+ '/'.join(sorted(dates[p])) for p in (fork,mlink)),style='small'); rows=[[tr('指标','Metric'),'fork','mlink',tr('变化','Change')]]
    def pair(label,get,unit):
        a,b=[get(p) for p in (fork,mlink)]; rows.append([label+' / '+unit,f(a),f(b),pct(a,b)])
    for lang in langs: pair(langs[lang]+' print',lambda p:sample(p,lang,'print_ms'),'ms')
    pair('Python Ready',lambda p:sample(p,'python','ready_ms'),'ms')
    for key,label,unit in [('short_ms',tr('短命令','Short command'),'ms'),('cpu_ms','SHA-256','ms'),('io_ms',tr('32 MiB 写入','32 MiB write'),'ms'),('throughput',tr('并发 2 吞吐','Concurrency-2 throughput'),'task/s')]:pair(label,lambda p:resources[p][key],unit)
    for stage,label in [('live2',tr('双沙箱不同内容新增磁盘','Two guests, differing content: added disk')),('paused2',tr('双沙箱保存后新增磁盘','Two guests after save: added disk'))]:rows.append([label+' / MiB',f(resources[fork]['storage']['different'][stage]['extent_mib'])+' *',f(resources[mlink]['storage']['different'][stage]['extent_mib']),tr('跨机','Cross-host')])
    pair(tr('50 沙箱产品总 PSS','Total product PSS at 50'),lambda p:resources[p]['memory']['levels']['50'],'MiB'); pair(tr('删除确认','Deletion acknowledgment'),lambda p:sample(p,'python','delete_ms'),'ms'); pair(tr('每沙箱新增 PSS','Added PSS per guest'),lambda p:(resources[p]['memory']['levels']['50']-resources[p]['memory']['levels']['0'])/50,'MiB');
    for key,label in [('snapshot_ms',tr('暂停保存','Pause and save')),('print_ms',tr('恢复至 print','Restore to print'))]:
        rows.append([label+' local / ms (113)',f(med(r[key] for r in local113)),f(med(r[key] for r in snaps[mlink])),pct(med(r[key] for r in local113),med(r[key] for r in snaps[mlink]))])
    pair(tr('同时发出 256 个请求至全部 print','Simultaneous: all 256 prints'),lambda p:bursts[p,0]['print']['all_256_ms']/1000,'s');table(rows,[240,85,85,100]);text('变化 = (fork / mlink − 1) × 100%。耗时与占用越低越好，吞吐越高越好。* 两项磁盘值为 108 优化版专项实测（3 组）；mlink 为 113 数据，跨机器不计算对比百分比。','Change = (fork / mlink − 1) × 100%. Lower latency and footprint are better; higher throughput is better. * Disk entries use optimized fork on host 108 (3 pairs); mlink used host 113. Cross-host percentage comparisons are omitted.','small')
    text('三语言 print 较快；Python Ready、删除确认和并发 2 吞吐仍有不足。保存/恢复的 local 使用 113 既有专项批次，remote 为本轮数据；两种路径不混比。108 优化版在正文单独列明，不能当作 113 实测。','All three prints are faster; Python Ready, delete acknowledgment and concurrency-2 throughput remain weaker. Local persistence uses the retained 113 batch; remote uses the current batch. The paths are not conflated. Optimized host-108 results appear separately in the body, not as measurements on 113.','small')
    for lang in langs:
        page(langs[lang]+' 启动',langs[lang]+' startup'); provenance(); text('Ready：客户端收到原生探针标记。print：从创建调用前到客户端收到解释器随机标记。每格排除一次预热，计 50 次。默认热路径对比并非相同的缓存实现。','Ready ends at client receipt of the native probe marker. Print spans the create call through client receipt of the real interpreter marker. Each cell excludes one warmup and includes 50 observations. Default warm paths use different cache implementations.'); data=[];rr=[['Product / mode','Ready p50','Print p50','Print p95','Print p99']]
        for (p,l,m),groupdata in sorted(cells.items(),key=lambda entry:(entry[0][2]!=reference(entry[0][0]),order.index(entry[0][0]),entry[0][2])):
            if l!=lang:continue
            vals=stats([v['print_ms'] for v in groupdata]);ready=med(v['ready_ms'] for v in groupdata);label=names[p]+' / '+m.replace('product_default_warm','default');rr.append([label,f(ready)]+[f(v) for v in vals[:3]]);data.append((label,ready,vals[0]))
        table(rr,[175,80,85,85,85]); story.append(charts.bars(data,'Ready / print (ms)',english,log=True));text(relative(sample(fork,lang,'print_ms'),sample(mlink,lang,'print_ms')),style='small')
    page('执行、CPU/IO 与并发任务','Execution, CPU/IO and concurrent tasks'); provenance()
    table([[tr('产品','Product'),tr('短命令 ms','Short ms'),'SHA-256 ms',tr('32 MiB IO ms','32 MiB IO ms'),tr('并发 2 任务/秒','2 concurrent tasks/s')]]+[[names[p]]+[f(resources[p][k]) for k in ['short_ms','cpu_ms','io_ms','throughput']] for p in order])
    text('短命令：五轮，每轮八次，先取每轮中位数再取中位数。SHA-256：预先准备 256 MiB 数据后计时计算哈希。32 MiB IO：包含生成数据、哈希、写入和 fsync 的实际耗时。','Short command: five rounds of eight, median of round medians. SHA-256: hash 256 MiB after input preparation. The 32 MiB IO test includes data generation, hashing, writing and fsync.')
    text('并发 2：始终最多同时进行两个任务，一共完成八个任务；每个任务包含创建沙箱、执行 print、计算哈希及删除。任务数除以整组实际耗时，得到每秒完成任务数；越高越好，不是单次命令耗时。','Concurrency 2: at most two tasks run simultaneously, eight in total. Each task creates a sandbox, executes print and hashing, then deletes it. Completed task count divided by elapsed batch time gives tasks/second; higher is better. This is not one command latency.')
    page('内存：业务沙箱数量与数组写入','Memory: guest count and array writes'); provenance()
    table([[tr('产品','Product')]+[tr(f'{n} 个业务沙箱时总 PSS',f'Total PSS at {n} guests') for n in [0,1,10,50]]]+[[names[p]]+[f(resources[p]['memory']['levels'][str(n)]) for n in [0,1,10,50]] for p in order])
    text('单位 MiB。0 表示预备池已就绪、没有业务沙箱；1/10/50 表示同时保留对应数量业务沙箱时产品相关宿主进程的总 PSS，不是每个沙箱的占用。预备池产品按 64 槽配置；统计包含 VMM、API、专用存储/缓存及启用的磁盘代理等受测服务进程。PSS 按使用者比例分摊共享页，不含未映射的宿主页缓存。','MiB. Zero means reserves are ready with no business guests. 1/10/50 are total host-process PSS with that many live guests, not per-guest usage. Pooled products are configured for 64 reserves. Scope covers measured service processes, including VMM, API, dedicated stores/cache and active disk proxy. PSS apportions shared pages and excludes unmapped host page cache.')
    table([[tr('产品','Product'),tr('默认零值数组：总 PSS 增量','Zero-initialized array: total PSS delta'),tr('全写字节 100：总 PSS 增量','Byte 100 filled: total PSS delta'),tr('全写随机字节：总 PSS 增量','Random filled: total PSS delta')]]+[[names[p]]+[f(resources[p]['memory']['arrays'][k]) for k in ['default','100','random']] for p in order])
    text('每种模式在 50 个沙箱中各运行一个 Python 进程，各分配 20 MiB bytearray。默认模式不额外填充；100 模式将每个字节写为数值 100；random 模式用随机字节填满。单位 MiB，增量＝数组阶段总 PSS 中位数－仅运行 Python、不分配数组阶段的总 PSS 中位数。','Each mode runs one Python process in each of 50 guests and allocates a 20 MiB bytearray per process. Default performs no extra fill; 100 fills each byte with value 100; random fills random bytes. MiB delta = median total PSS in the array phase minus median total PSS in the Python-only phase.')
    text('程序保持数组并睡眠 15 秒；每约 0.4 秒采样，取所有任务共同存活区间内至少三次采样的中位数。该指标是 50 个沙箱的总增量，不是单个数组的大小，不能单凭结果证明去重。','Processes retain arrays during a 15-second sleep. Samples are collected about every 0.4 seconds; at least three within the shared live interval form the median. This is the aggregate increase across 50 guests, not one array size, and is not by itself proof of deduplication.')
    page('磁盘：两个沙箱写入与保存','Disk: writes and saves of two guests'); provenance()
    table([[tr('产品','Product'),tr('相同内容：运行时新增','Same content: live added'),tr('相同内容：保存后新增','Same content: saved added'),tr('不同内容：运行时新增','Different content: live added'),tr('不同内容：保存后新增','Different content: saved added')]]+[[names[p]]+[f(resources[p]['storage'][kind][stage]['extent_mib']) for kind in ['same','different'] for stage in ['live2','paused2']] for p in order])
    text('单位 MiB。两个沙箱各写入并 fsync 32 MiB，相同/不同指两者写入的内容。基线是创建两个业务沙箱之前、模板及预备池已就绪时的受测目录占用。运行时与保存后都减同一个基线，不能将两列相加。','MiB. Each of two guests writes/fsyncs 32 MiB; same/different describes their contents. Baseline is the measured directory footprint before creation, with templates/reserves ready. Both live and saved stages subtract that same baseline; do not add the two columns.')
    text('统计受测目录集合中唯一物理区段的新增量，FIEMAP 对共享 reflink 区段去重，不是逻辑文件大小或简单相加 du。每种内容测三组，先分别减基线，再取中位数。fork 来自 108 优化版专项，其他五方来自 113；机器和预备槽数不同，因此不计算跨机百分比。','FIEMAP counts added unique physical extents across measured roots, deduplicating shared reflink extents; this is not logical file length or a sum of du values. Three pairs per content type, median of per-pair baseline deltas. Fork uses the optimized host-108 batch; other products use 113. Host and reserve counts differ, so cross-host percentages are omitted.')
    page('双沙箱磁盘：已有原始数据核对','Two-guest disk: retained raw evidence')
    text('每组创建两个沙箱，各写入并 fsync 32 MiB；不同内容组使用不同数据，相同内容组使用相同数据。基线为创建前已存在模板与预备池；live2 为两实例写入后，paused2 为两实例均保存后。两个阶段均减同一基线，保存值不是在 live2 之上再次增加。','Each pair creates two guests and writes/fsyncs 32 MiB per guest, using identical or differing content. Baseline includes the pre-existing template and reserve pool. live2 is after both writes; paused2 is after both saves. Both subtract the same pre-create baseline; saved footprint is not an additional delta above live2.')
    table([[tr('批次 / 模式','Batch / mode'),tr('相同内容：运行时新增','Same content: live added'),tr('相同内容：保存后新增','Same content: saved added'),tr('不同内容：运行时新增','Different content: live added'),tr('不同内容：保存后新增','Different content: saved added')]]+[[label]+[f(storage_batches[k][kind][stage]['extent_mib']) for kind in ['same','different'] for stage in ['live2','paused2']] for k,label in [('optimized108',tr('108 优化版 / local','108 optimized / local')),('previous113',tr('113 较早版本 / local','113 earlier / local'))]])
    text('单位 MiB；每种内容 3 组，取各组增量的中位数。用 FIEMAP 统计受测目录集合内唯一物理区段，共享 reflink 区段不重复计数；不是逻辑文件大小，也不是单实例值乘二。每组都检查成功及销毁后无剩余实例。','MiB; three pairs per content type, median of per-pair deltas. FIEMAP counts unique physical extents across the measured roots, avoiding duplicate reflink extents. These are neither logical sizes nor twice a single-guest measurement. Each pair passed success and no-remaining-instance checks.')
    text('108 使用 2 个预备槽，113 对比数据使用 64 槽。CPU/内存为 2 vCPU / 2 GiB，使用固定 Python 镜像。108 为已保留的私有 CoW 与 QCOW 复用优化；113 较早批次尚未包含该本地空间优化。因此这里只补充已有测量，不将跨机器、跨版本差异归因于单项优化，也不称为本轮 113 新测。','Host 108 used two reserves; the host-113 comparator batch used 64. The workload uses 2 vCPUs/2 GiB and the pinned Python image. The retained 108 implementation includes private CoW and QCOW reuse; the earlier 113 batch predates this local footprint optimization. This supplements existing measurements, not a fresh 113 run; cross-host/version changes are not attributed to one optimization.')
    page('持久化：local 与 remote 分开比较','Persistence: separate local and remote paths')
    def statpair(rs,k): return f(med(r[k] for r in rs))+' / '+f(max(r[k] for r in rs))
    persist_rows=[[tr('产品 / 路径 / 批次','Product / path / batch'),tr('保存 ms：中位 / 最大','Save ms: median / max'),tr('恢复 API ms：中位 / 最大','Restore API: median / max'),tr('恢复 print ms：中位 / 最大','Restore print: median / max')]]
    cohorts=[('fork / local / 113 retained',local113),('mlink / native API / 113 retained',snaps[mlink]),('fork / remote / 113 current',snaps[fork]),('fork / local optimized / 108',local108)]+[(names[p]+' / native API / 113 retained',snaps[p]) for p in order[2:]]
    for label,rs in cohorts:persist_rows.append([label]+[statpair(rs,k) for k in ['snapshot_ms','restore_api_ms','print_ms']])
    table(persist_rows)
    text('每行 10 次测量，另排除 1 次预热；2 vCPU / 2 GiB，固定 Python 镜像。保存前有 32 MiB 活跃随机内存进程和已 fsync 的 32 MiB 文件。保存从暂停请求到确认；恢复 API 从恢复请求到 API 返回；恢复 print 从恢复请求到客户端收到新启动 Python 解释器的随机标识。核验进程/文件状态及销毁。','Each row has 10 measurements plus one excluded warmup; 2 vCPUs/2 GiB and pinned Python image. Before save: a process holding 32 MiB random RAM and a fsynced 32 MiB file. Save spans pause request to acknowledgment; restore API ends at API return; restore print ends at receipt of a random marker from a newly started Python interpreter. Process/file state and deletion are checked.')
    text('113 本轮配置未指定 checkpoint_mode，源码默认 Remote，走 Manifest/chunk；旧表中的 2,563 ms 保存及 3,150 ms 恢复属于此路径。local 使用本地原生载体，113 既有批次和 108 优化版单列，未将 108 改善冒充为 113 结果。其他产品展示其原生保存 API，并非强行等同 fork remote。','The current 113 configuration omits checkpoint_mode; source default is Remote, using Manifest/chunks. The former 2,563 ms save and 3,150 ms restore numbers belong to that path. Local uses native local carriers. Retained 113 and optimized 108 are separate; 108 improvements are not presented as 113 measurements. Other products use their native persistence APIs, not an assumed match to fork remote.')
    text('恢复保留自然保存后缓存，没有驱逐或重启宿主；不是冷启动恢复测试。数据来自不同批次；跨机器或 local 对 remote 不计算性能百分比。','Restores retain natural post-save cache; no eviction or host reboot. This is not cold restore. Batches differ; cross-host and local-versus-remote performance percentages are omitted.')
    page('Python：从运行中父沙箱 fork','Python: fork a running parent')
    timeline(live['representative'],tr('代表性请求：阶段实际耗时','Representative request: elapsed stage times'))
    text(tr('50 次真实 HTTP fork，中位数 / ms：','50 real HTTP fork requests; medians / ms: ')+', '.join(label+' '+f(live['metrics'][k]['median']) for k,label in [('parent_pause_ms',tr('父暂停','Parent pause')),('ready_ms',tr('子 ready','Child ready')),('print_ms',tr('子 print','Child print'))]))
    text('横轴从发出 fork 请求开始为 0，子 ready 与子 print 均相对该时刻。重叠阶段纵向分开。父暂停单独统计；两种销毁顺序均验证独立文件和进程继续运行。','Time zero is the fork request. Child ready and child print are relative to it; overlapping stages use separate lanes. Parent pause is measured separately. Both destruction orders verify independent files and continued processes.')
    page('预备池、删除与容量','Reserves, deletion and capacity');provenance(); serial=cells[fork,'python','local_warm']; previous=next(r for r in pool['samples'] if r['product']==mlink);table([[tr('口径','Measure'),'fork','mlink'],[tr('预备槽 / 准备并行度','Starting reserves / preparation workers'),'64 / 8','64 / 8'],[tr('删除确认 p50 / ms','Delete acknowledgment p50 / ms'),f(sample(fork,'python','delete_ms')),f(sample(mlink,'python','delete_ms'))],[tr('创建至池恢复 p50 / ms','Create through full pool p50 / ms'),f(med(r['lifecycle_through_refill_ms'] for r in serial)),f(med(r['create_through_full_pool_ms'] for r in previous['details']))],[tr('启动准备：接口记录 / ms','Startup preparation: API field / ms'),f(med(r['pool_before']['state']['preparation_ms'] for r in serial)),'—'],[tr('首槽开始至 64 槽就绪 / ms','First slot start to 64 ready / ms'),f(fork_pool['first_to_full_ms']),f(pool['mlink']['preparation']['first_slot_start_to_64_ready_ms'])],[tr('单槽准备中位数 / ms','Single slot preparation median / ms'),f(fork_pool['single_slot_median_ms']),f(pool['mlink']['preparation']['single_slot_ms']['median'])],[tr('空闲槽专属进程 / MiB 每槽','Idle slot-owned process PSS / MiB per slot'),f(previous_fork_slot['slot_processes_average_pss_mib'])+' *',f(slot['slot_processes_average_pss_mib'])]], [300,105,105]);text('fork 的准备字段是运行时状态值，不是 50 次独立启动，也未证明与 mlink 计时边界相同。删除至确认不含后续等待。两方每组 256 个成功实例保留到批次结束，证明该工作负载容量，不证明理论最大容量。','The fork preparation field is runtime state, not 50 independent pool starts. Its boundaries are not established as equivalent to mlink’s. Delete acknowledgment excludes later waits. Retaining 256 successful guests demonstrates workload capacity, not the theoretical limit.');text('并发失败：此前 off 与 UFFD 在间隔 0/10/25 ms 的批次中遇到分配 runner 的 5 秒内部超时。它们的失败请求不进入全部完成耗时。','In the earlier off and UFFD batches at 0/10/25 ms spacing, runner assignment hit its internal five-second deadline. Failed requests preclude an all-256 completion time.');table([['Product','Spacing / ms','Failed']]+[[names[row['product']],row['interval_ms'],row['failed']] for row in failures if row['product']!=fork and row['failed']]);
    text('补齐值来自已保存的事件：fork 同一有效 epoch 的 64 个 startup 槽，首个 prepare_started 到最后一个 prepared；单槽时间取这 64 个成功槽的中位数。并行数 8，不能将单槽耗时相加当作总时间。* fork 每槽 PSS 采用此前 113 专项（非本轮）：只统计槽专属进程，排除共享控制面，再除以 64；不是产品总 PSS 除以 64。','Filled values use retained events: 64 startup slots in one valid fork epoch, first prepare_started to last prepared. Single-slot time is the median of those 64 successes. Eight workers run concurrently, so durations are not summed as total elapsed time. * Fork per-slot PSS uses the earlier 113 dedicated batch, not this run: slot-owned processes only, excluding common services, divided by 64; not total product PSS/64.')
    text('256 请求结果来自提高专用 VMM 文件描述符上限后的有效批次；这不证明长期无 FD 泄漏，持续观测因撤除部署中断。','The accepted 256-request batch used a raised dedicated VMM descriptor limit. This is not proof of no long-term FD leak; deployment retirement interrupted that observation.','small')
    for interval in charts.INTERVALS:
        page(f'256 请求：间隔 {interval} ms',f'256 requests: {interval} ms spacing');provenance();table([['Product','Print n/256','All print / s','Retained']]+[[names[p],str(bursts[p,interval]['print']['completed']),f(bursts[p,interval]['print']['all_256_ms']/1000 if bursts[p,interval]['print']['all_256_ms'] is not None else None),str(len(bursts[p,interval]['retained_alive_before_cleanup']))] for p in order]);text('单批次；成功实例保留至所有请求结束。只有 256 个全部打印才报告总耗时。间隔按完成顺序，不按派发顺序。','One batch per cell. Successful guests remain until all requests settle. Total time requires all 256 prints. Gaps follow completion order, not dispatch order.');story.append(charts.startup_charts(out,english,interval)[1]);
        page(f'槽位准备：请求间隔 {interval} ms',f'Slot preparation: request spacing {interval} ms')
        rd=charts.refill_data(out,interval)
        story.append(charts.refill_chart(out,english,interval,phase='before_cleanup'));story.append(charts.refill_chart(out,english,interval,phase='after_cleanup'))
        table([[tr('类型','Type'),tr('销毁前完成次数','Completed before cleanup'),tr('销毁后完成次数','Completed after cleanup')]]+[[name,str(sum(e['phase']=='before_cleanup' and e['kind']==kind for e in rd[prod]['events'])),str(sum(e['phase']=='after_cleanup' and e['kind']==kind for e in rd[prod]['events']))] for prod,kind,name in [(fork,'refill','fork refill'),(mlink,'floor','mlink floor'),(mlink,'elastic','mlink elastic')]])
        text('仅纳入首次请求发出后开始、观察结束前完成的成功 VM 准备事件；按执行唯一键去重，排除初始建池及失败。fork 取 reason=refill，mlink 按基础池 Floor 和弹性扩容 Elastic 分开。准备可与请求并行，数量不等于请求数。两图按完成时刻相对统一销毁开始分组，跨界任务归销毁后；不把它解释成销毁触发的因果关系。','Only successful VM preparation begun after first dispatch and completed by observation end is included. Unique executions are deduplicated; initial preparation and failures are excluded. Fork uses reason=refill; mlink separates Floor from Elastic expansion. Preparation overlaps requests; counts need not equal request count. Panels classify completion relative to cleanup start; straddling jobs belong to after-cleanup, without implying cleanup caused them.')
(out/'refill-audit.json').write_text(json.dumps({str(i):charts.refill_data(out,i) for i in charts.INTERVALS},indent=2))
for item in story:
    if isinstance(item,Paragraph):
        for fragment in item.frags:
            if hasattr(fragment,'text'):fragment.text=fragment.text.replace('−','-')
ReportDoc(str(out/'sandbox-sixway-zh-en.pdf'),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=38,bottomMargin=40).build(story,onFirstPage=footer,onLaterPages=footer);(out/'sources.json').write_text(json.dumps(files,indent=2))
