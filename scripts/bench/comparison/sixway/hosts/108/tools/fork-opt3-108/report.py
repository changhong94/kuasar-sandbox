import json,statistics,hashlib,shutil,difflib,subprocess
from pathlib import Path
M=Path('/opt/bench108');R=M/'results/fork-opt3-108';Q=M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'
s=json.loads((R/'stages.json').read_text());selected='round3';a=s[selected]['fork_median_ms'];b=s['baseline']['fork_median_ms'];val=json.loads((R/'validation.json').read_text());assert val['success'] and val['grandchild_after_parent_destroy']
loads={}
for variant in s:
 rows=[json.loads(p.read_text()) for p in (R/variant).glob('[0-9]*.json')];assert len(rows)==20 and all(x['success'] and x['destroyed'] and x['attempts']==1 for x in rows)
 xs=sorted([json.loads(p.read_text()) for p in (R/variant).glob('*-host.json')],key=lambda x:x['time_ns']);cpu=[]
 for x,y in zip(xs,xs[1:]):
  u=list(map(int,x['stat'].splitlines()[0].split()[1:9]));v=list(map(int,y['stat'].splitlines()[0].split()[1:9]));d=[n-m for m,n in zip(u,v)];cpu.append(100*(1-(d[3]+d[4])/sum(d)))
 loads[variant]={'mean_cpu_busy_percent':statistics.mean(cpu),'first_loadavg':xs[0]['loadavg'],'last_loadavg':xs[-1]['loadavg']}
(R/'source').mkdir(exist_ok=True);diff=[]
for name in ['image-mount.c','image_pool.py','slot_disk.py','durable_state.py','template_pool.py','vm_backend.py']:
 shutil.copy2(Q/name,R/'source'/name)
 diff.extend(difflib.unified_diff((R/'before'/name).read_text().splitlines(True),(Q/name).read_text().splitlines(True),fromfile='before/'+name,tofile='after/'+name))
for name in ['README.md','test_durable_state.py']:shutil.copy2(Q/name,R/'source'/name)
(R/'changes.patch').write_text(''.join(diff));shutil.copy2(M/'deploy/fork/supervisor.py',R/'supervisor.final.py');shutil.copy2(M/'deploy/fork/images.json',R/'images.final.json')
sha={}
for p in [M/'deploy/fork/bin/cloud-hypervisor',M/'deploy/fork/bin/sandboxer',M/'deploy/fork/bin/image-mount',M/'assets/python-base.ext4',M/'assets/python-base-fork-opt3-v2.erofs']:
 with p.open('rb') as f:sha[str(p)]=hashlib.file_digest(f,'sha256').hexdigest()
previous=json.loads((M/'results/fork-opt2-108/manifest.json').read_text())['sha256']
for p in [M/'deploy/fork/bin/cloud-hypervisor',M/'deploy/fork/bin/sandboxer',M/'assets/python-base.ext4']:assert sha[str(p)]==previous[str(p)]
assert not list((M/'data/fork').rglob('memory.img'))
records=json.loads((M/'data/fork/adapter-state.json').read_text());assert len(records)==64 and all(v['pool_state']=='ready' for v in records.values())
files=list((M/'data/fork/slot-disks').glob('e2b-*.raw'));assert len(files)==64 and all(p.is_file() and not p.is_symlink() and p.stat().st_blocks==0 for p in files)
assert {str(p) for p in files}=={v['slot_disk'] for v in records.values()}
loops=[]
for p in Path('/sys/block').glob('loop*/loop/backing_file'):
 try:text=p.read_text().strip()
 except FileNotFoundError:continue
 if '/deploy/fork/loop-images/' in text:loops.append(text)
assert not loops,loops
pss=0;fds=[]
for v in records.values():
 p=Path('/proc',str(v['pid']));pss+=int(next(l for l in (p/'smaps_rollup').read_text().splitlines() if l.startswith('Pss:')).split()[1]);fds.append(len(list((p/'fd').iterdir())))
pe=[json.loads(l) for l in (M/'data/fork/adapter-state.json.pool-events.jsonl').read_text().splitlines()];start=next(e for e in pe if e['event']=='startup_complete');refill=[e for e in pe if e['event']=='prepared' and e['reason']=='refill']
prep={'pool64_startup_ms':start['elapsed_ms'],'refill_count':len(refill),'refill_work_median_ms':statistics.median(e['elapsed_ms'] for e in refill),'replacement_including_wait_median_ms':statistics.median(e['replacement_ms'] for e in refill),'catalog':json.loads((M/'data/fork/slot-disks/preparation.json').read_text()),'filesystem_driver':json.loads((M/'deploy/fork/filesystem-preparation.json').read_text()),'helper':json.loads((M/'deploy/fork/mount-helper-preparation.json').read_text())}
(R/'preparation.json').write_text(json.dumps(prep,indent=2));(R/'resources.json').write_text(json.dumps({'ready':64,'assigned':0,'vmm_pss_kib':pss,'vmm_fd_min':min(fds),'vmm_fd_max':max(fds),'experimental_bound_loops':loops,'slot_device_count':64,'ready_device_allocated_bytes':0},indent=2))
for n in ['kuasar-fork','kuasar-mlink']:shutil.copy2(M/'results'/('audit-'+n+'.json'),R/('audit-'+n+'.json'))
rev=subprocess.check_output(['git','-C',str(M/'tools/fork-opt3-108/erofs-utils'),'rev-parse','HEAD'],text=True).strip()
manifest={'selected':'round3','goal_achieved':False,'load':loads,'sha256':sha,'erofs_utils_commit':rev,'image_oci_manifest':json.loads((M/'deploy/fork/images.json').read_text())['base']['manifest'],'tests_final':'56 passed, no skips','memory_img_files':[],'ksm_run':Path('/sys/kernel/mm/ksm/run').read_text().strip()};(R/'manifest.json').write_text(json.dumps(manifest,indent=2))
# Match mlink logs to exact request sandbox IDs, not adjacent refill events.
ml=s[selected]['mlink_restore_ms']
labels={'baseline':'本轮基线','round1':'1：64KiB预取窗口','round2':'2：无压缩EROFS','round3':'3：EROFS + WAL/EXTRA','round4':'4：LZ4压缩EROFS','round5':'5：原生持久库/非旋转队列','loop-followup':'补充：只读loop后端'}
lines=['108：挂载/预取五轮优化与mlink对比','', '结论：未实现超过mlink的目标。五轮中第3轮最好，已恢复并部署该版。另补做一组只读loop后端验证，未改善，已撤回；没有隐藏失败版本或重跑后挑最低样本。','', '口径：同一OCI Python镜像 sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79；1vCPU、2048MiB、64槽、1000ms补槽等待。','每个版本、每个产品各10次，并发2，五轮交错；起点创建请求，终点客户端收到随机shell printf READY。不含Python解释器启动。SDK继续用 /bin/bash -l -c，mlink继续原 /bin/sh -c。','磁盘表示从ext4改为无压缩EROFS，磁盘文件SHA256因此改变；OCI内容未变。5584个文件/目录/链接的内容、UID/GID、模式、mtime、链接目标、xattrs、设备号逐项相同。老版mkfs.erofs不能保留mtime的产物未进入正式测试，改用已固定提交的erofs-utils --preserve-mtime。','', '端到端中位数(ms)：','版本                              fork       mlink']
for v in labels:
 d=s[v]['end_to_end'];lines.append(f'{labels[v]:28s} {d["kuasar-fork"]["median_ms"]:10.3f} {d["kuasar-mlink"]["median_ms"]:10.3f}')
lines += ['',f'保留版相对本轮基线下降 {(1-a["total"]/b["total"])*100:.1f}%；同轮仍比mlink慢 {(a["total"]/s[selected]["end_to_end"]["kuasar-mlink"]["median_ms"]-1)*100:.1f}%。每组只有10次；轮间负载/调度波动存在，不能以该表声称稳定尾延迟或将多个版本最低值拼成结果。','', '关键阶段：本轮基线 -> 保留第3轮，中位数ms（中位数不能相加）：']
for label,k in [('领取槽位（含私有分配持久化）','pool_lease'),('镜像绑定及fsync','image_disk_attach'),('挂载RPC，含预取','image_mount'),('持久发布','image_publish'),('首次命令到客户端收到','first_command_client'),('端到端','total')]:lines.append(f'{label:29s} {b[k]:9.3f} -> {a[k]:9.3f}')
lines+=['',f'保留版helper内：设备/失效检查 {a["ready_us"]:.3f}ms，只读lower挂载 {a["ext4_us"]:.3f}ms，overlay {a["overlay_us"]:.3f}ms，helper目录/绑定 {a["helper_us"]:.3f}ms，dev/proc/sys绑定 {a["bind_us"]:.3f}ms，检查 {a["check_us"]:.3f}ms，预取 {a["prefetch_us"]:.3f}ms。日志ext4_us是历史字段名，第2/3轮实际是EROFS lower。','挂载RPC没有得到净改善：32.077 -> 33.120ms。明确收益主要是持久化协议的实现成本下降，不能把端到端收益说成挂载瓶颈已经解决。','', 'mlink实际上少做了什么：','现有tt_timing日志已足够，未修改/重启mlink。按每个benchmark sandbox ID匹配pico_restore，共10条；没有将后台prepared-storage事件混进请求统计。',f'同轮设备领取 {ml["device_acquire_us"]:.3f}ms，VMM恢复 {ml["vmm_restore_us"]:.3f}ms，guest就绪 {ml["guest_ready_us"]:.3f}ms，发布 {ml["publish_us"]:.3f}ms，内部restore总计 {ml["total_us"]:.3f}ms。这不等于客户端端到端耗时。','本次mlink走restore_kind=full，恢复已有文件系统/应用状态；fork通用槽位在领取时接入应用镜像，仍需建立guest VFS状态并读取启动依赖。mlink日志的后台存储预备使用EphemeralWarm、disk_sync_us=0；fork没有模仿删除同步屏障。','参考源码：src/kuasar-mlink/private/kuasar-mlink/thinkthread/crates/ttcom-pico-runtime/src/runtime.rs 的activate_restore与pico_restore timing字段。','', '尝试与结果：','第1轮缩小预取窗口，挂载变快但首次命令回退，拒绝。第2轮EROFS减少lower元数据成本但预取仍主导。第3轮WAL仍synchronous=EXTRA，每次COMMIT在确认前同步；所有权、只读镜像fsync、挂载后发布和失败隔离均保留。','第4轮压缩在这个guest/工作负载中增加预取耗时，拒绝。第5轮原生持久库与非旋转队列并未使端到端优于第3轮，已撤回默认部署。','补充loop路径通过原子配置、只读同容量backing切换、AUTOCLEAR和引用生命周期测试，但切换阶段约8.5ms抵消缓存收益；恢复reflink路径，活动实验loop设备已清理。不能据此将剩余开销单独归因于新inode页缓存。','', '补充诊断（单个样本，不是10次中位数）：','diagnostic.json记录挂载RPC约13.15ms、挂载CPU约2.39ms、预取CPU约7.34ms、预取墙钟约8.44ms，创建阶段VMM minor faults增加1229，major faults为0。其负载与正式并发组不同，不能用13.15ms替代正式33.12ms，也不能据此认定所有时间都是磁盘等待。','', '准备成本和资源：',f'恢复后64槽准备 {prep["pool64_startup_ms"]:.1f}ms；补槽实际工作中位数 {prep["refill_work_median_ms"]:.1f}ms，含固定等待到替补就绪 {prep["replacement_including_wait_median_ms"]:.1f}ms（{prep["refill_count"]}次事件）。',f'已有镜像缓存校验 {prep["catalog"]["cache_validation_ms"]:.1f}ms；通用文件系统模块准备 {prep["filesystem_driver"]["elapsed_ms"]:.2f}ms；静态helper上传 {prep["helper"]["elapsed_ms"]:.2f}ms。镜像转换及一致性校验是单独准备步骤，见erofs-preparation.log。',f'64槽VMM合计PSS约{pss/1024:.1f}MiB，FD范围{min(fds)}..{max(fds)}；64个未绑定稀疏设备数据块实际分配0。镜像缓存可有每镜像文件，但没有每镜像VM池。','', '验证：','56项最终回归测试通过，无跳过；WAL提交前强杀回滚、提交后/JSON投影前强杀恢复均通过。另有loop独立测试仅归档，不作为生产路径。',f'真实Linux guest继承运行中的Python PID/nonce和16MiB内存；父写20、子写30，文件写入独立；抽样共享物理页帧{val["shared_sampled_pfns"]}。父先销毁、子先销毁、父销毁后从子派生孙且再销毁子，存活方均可继续执行。','fork与mlink最终清理审计通过，恢复64个ready槽，0个assigned；无遗留实验loop映射。没有memory.img、没有全量复制RAM；VMM/sandboxer和原始ext4镜像二进制SHA256未改。只操作本任务所属fork部署与测试沙箱，Docker/containerd启动时间仍为10月30日，mlink未重启。','', '尚未完成：超过mlink的性能目标，以及将挂载RPC从约32ms显著降低。需要进一步定位guest首次VFS/页缓存建立和并发调度成本，当前证据不足以把剩余19ms预取归因于单一原因。','', '证据：stages.json、baseline/、round1..round5/、loop-followup/、各组server/mlink日志、diagnostic.json、filesystem-equivalence.json、validation.json、tests-final.log、manifest.json、preparation.json、resources.json、changes.patch、source/、experimental/。','接口参考（仅loop实验）：https://man7.org/linux/man-pages/man4/loop.4.html 。']
(R/'REPORT.txt').write_text('\n'.join(lines)+'\n');(R/'complete.json').write_text(json.dumps({'experiment_rounds_completed':5,'additional_backend_benchmark_groups':1,'samples_per_product_per_group':10,'selected_variant':'round3','performance_goal_achieved':False,'final_validation':True,'ready_pool':64},indent=2))
print(json.dumps({'preparation':prep,'selected_ms':a['total'],'control_ms':s[selected]['end_to_end']['kuasar-mlink']['median_ms']},indent=2))
