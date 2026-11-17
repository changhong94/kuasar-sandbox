from pathlib import Path
import json,statistics,hashlib,shutil,difflib,subprocess
M=Path('/opt/bench108');R=M/'results/fork-opt2-108';Q=M/'src/kuasar-fork/kuasar-io/kuasar/integrations/e2b'
stages=json.loads((R/'stages.json').read_text());b=stages['baseline']['median_ms'];a=stages['after']['median_ms']
loads={}
for variant in ['baseline','after','prototype-no-readahead','prototype-host-readahead','prototype-serial-guest-readahead']:
 rows=[json.loads(p.read_text()) for p in (R/variant).glob('[0-9]*.json')];assert len(rows)==20 and all(x['success'] and x['destroyed'] for x in rows)
 xs=sorted([json.loads(p.read_text()) for p in (R/variant).glob('*-host.json')],key=lambda x:x['time_ns']);cpu=[]
 for x,y in zip(xs,xs[1:]):
  u=list(map(int,x['stat'].splitlines()[0].split()[1:9]));v=list(map(int,y['stat'].splitlines()[0].split()[1:9]));d=[n-m for m,n in zip(u,v)];cpu.append(100*(1-(d[3]+d[4])/sum(d)))
 loads[variant]={'mean_cpu_busy_percent':statistics.mean(cpu),'first_loadavg':xs[0]['loadavg'],'last_loadavg':xs[-1]['loadavg']}
events=[json.loads(l[11:]) for l in (R/'after-server.log').read_text().splitlines() if l.startswith('E2B_TIMING ')]
parts=[json.loads(e['helper']) for e in events if e['stage']=='image_mount']
helper={k:statistics.median(d[k] for d in parts)/1000 for k in parts[0]}
records=json.loads((M/'data/fork/adapter-state.json').read_text());assert len(records)==64 and all(r['pool_state']=='ready' for r in records.values())
files=list((M/'data/fork/slot-disks').glob('e2b-*.raw'));assert {str(p) for p in files}=={r['slot_disk'] for r in records.values()}
assert all(p.stat().st_blocks==0 for p in files)
pe=[json.loads(l) for l in (M/'data/fork/adapter-state.json.pool-events.jsonl').read_text().splitlines()]
startup=next(e for e in pe if e['event']=='startup_complete');refill=[e for e in pe if e['event']=='prepared' and e['reason']=='refill']
prep={'pool_64_startup_ms':startup['elapsed_ms'],'refill_n':len(refill),'refill_work_median_ms':statistics.median(e['elapsed_ms'] for e in refill),'replacement_including_delay_median_ms':statistics.median(e['replacement_ms'] for e in refill),'slot_disk':json.loads((M/'data/fork/slot-disks/preparation.json').read_text()),'helper_upload':json.loads((M/'deploy/fork/mount-helper-preparation.json').read_text()),'cold_import':json.loads((R/'import-preparation.json').read_text())}
pss=0;fdcounts=[]
for r in records.values():
 pid=r['pid'];sm=Path(f'/proc/{pid}/smaps_rollup').read_text();pss+=int(next(l for l in sm.splitlines() if l.startswith('Pss:')).split()[1]);fdcounts.append(len(list(Path(f'/proc/{pid}/fd').iterdir())))
resources={'ready':64,'assigned':0,'unbound_sparse_devices':len(files),'device_logical_bytes_each':files[0].stat().st_size,'ready_device_allocated_bytes_total':sum(p.stat().st_blocks*512 for p in files),'pool_vmm_pss_kib':pss,'pool_vmm_fd_min':min(fdcounts),'pool_vmm_fd_max':max(fdcounts),'image_cache_logical_bytes':sum(p.stat().st_size for p in (M/'data/fork/slot-disks/images').glob('*.raw'))}
(R/'preparation.json').write_text(json.dumps(prep,indent=2));(R/'resources.json').write_text(json.dumps(resources,indent=2))
changes=[]
for name in ['image_pool.py','template_pool.py','vm_backend.py']:
 changes.extend(difflib.unified_diff((R/name).read_text().splitlines(True),(Q/name).read_text().splitlines(True),fromfile='before/'+name,tofile='after/'+name))
changes.extend(difflib.unified_diff((R/'image-mount.before.c').read_text().splitlines(True),(Q/'image-mount.c').read_text().splitlines(True),fromfile='before/image-mount.c',tofile='after/image-mount.c'))
(R/'changes.patch').write_text(''.join(changes));(R/'source').mkdir(exist_ok=True)
for name in ['image_pool.py','template_pool.py','vm_backend.py','slot_disk.py','image-mount.c','test_slot_disk.py','test_image_pool.py','durable_state.py','README.md']:shutil.copy2(Q/name,R/'source'/name)
shutil.copy2(M/'deploy/fork/supervisor.py',R/'supervisor.after.py')
for n in ['kuasar-fork','kuasar-mlink']:shutil.copy2(M/'results'/('audit-'+n+'.json'),R/('audit-'+n+'.json'))
sha={}
for p in [M/'deploy/fork/bin/image-mount',M/'assets/python-base.ext4',M/'deploy/fork/bin/cloud-hypervisor',M/'deploy/fork/bin/sandboxer']:
 with p.open('rb') as f:sha[str(p)]=hashlib.file_digest(f,'sha256').hexdigest()
assert not list((M/'data/fork').rglob('memory.img'))
previous=json.loads((M/'results/fork-opt-108/manifest.json').read_text())['sha256']
for p in [M/'assets/python-base.ext4',M/'deploy/fork/bin/cloud-hypervisor',M/'deploy/fork/bin/sandboxer']:assert sha[str(p)]==previous[str(p)]
(R/'manifest.json').write_text(json.dumps(dict(load=loads,sha256=sha,helper_median_ms=helper,ksm_run=Path('/sys/kernel/mm/ksm/run').read_text().strip(),tests='55 passed, no skips',memory_img_files=[]),indent=2))
val=json.loads((R/'validation.json').read_text());assert val['success'] and val['grandchild_after_parent_destroy']
lines=['108 通用池设备与首次执行优化','', '口径：同一 Python 基础镜像 manifest sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79；磁盘 SHA256 与上一轮完全相同。', '每个实现版本、每个产品各10次；并发2，五轮交错。计时为创建请求到客户端收到随机 shell printf READY，不含 Python 解释器启动。SDK仍运行 /bin/bash -l -c；mlink仍运行原 /bin/sh -c。', '总是单个64槽通用池、1000ms补槽等待；未建每镜像VM池，未操作其他人的进程。','', '端到端中位数(ms)：','版本                              fork       mlink']
for label,key in [('本轮优化前','baseline'),('预接设备原型，无预读','prototype-no-readahead'),('宿主预读原型','prototype-host-readahead'),('guest串行预读原型','prototype-serial-guest-readahead'),('最终并行预读版','after')]:
 d=json.loads((R/key/'summary.json').read_text());lines.append(f'{label:26s} {d["kuasar-fork"]["median_ms"]:10.3f} {d["kuasar-mlink"]["median_ms"]:10.3f}')
lines+=['',f'最终相对本轮基线下降 {(1-a["total"]/b["total"])*100:.1f}%；仍未追平mlink。保留全部原型数据，不从多个版本或样本中挑最低值当最终结果。10次样本不用于声称尾延迟保证。',f'宿主平均CPU忙碌：基线{loads["baseline"]["mean_cpu_busy_percent"]:.1f}%，最终{loads["after"]["mean_cpu_busy_percent"]:.1f}%；未控制其他工作负载，mlink对照也有波动。','', '阶段中位数(ms，不能直接相加)：']
for label,key in [('领取（含私有分配持久化）','pool_lease'),('设备添加/优化后reflink+fsync','image_disk_attach'),('挂载RPC（最终包含预读）','image_mount'),('持久发布','image_publish'),('客户端创建API','create_api'),('首次命令直到收到标识','first_command_client'),('其中guest命令执行','exec_guest'),('端到端','total')]:lines.append(f'{label:27s} {b[key]:10.3f} -> {a[key]:10.3f}')
lines+=['',f'最终helper内部：设备可用/缓存清除 {helper["ready_us"]:.3f} ms；文件系统挂载/绑定 {helper["mount_us"]:.3f} ms；有界并行预读 {helper["prefetch_us"]:.3f} ms。', '这里没有把预读移出请求计时；挂载RPC等待所有预读线程退出。FIRST command改善部分来自将读取前移到同一请求的挂载阶段，因此端到端改善远小于首次命令改善。','', '实现与安全顺序：', '1. 参考mlink提前准备设备资源的方式：每个通用槽位预接独立稀疏空盘，guest完成驱动/容量就绪和读预取配置；此时无应用镜像。', '2. 领取先持久化私有分配与镜像身份，再对已打开的空盘inode做FICLONERANGE，封为只读并fsync。guest执行BLKFLSBUF丢弃探测空盘时的缓存，再挂载只读ext4与独立overlay。成功后才持久发布；失败隔离销毁，不重用槽位。', '3. 源镜像在同一reflink文件系统中按SHA256校验缓存。请求中不全量复制磁盘，更不复制guest RAM；支持一个池接不同目录条目。该设备路径要求reflink文件系统，且只对从未交给用户的空白槽位绑定一次。', '4. 单个原生launcher替代chroot/sh/env多次exec，保留cwd、参数、环境及SDK登录shell。预取可选文件，每文件最多4MiB，缺文件跳过，不执行用户命令或profile；4个worker均join后返回。', '5. 运行中父沙箱fork绕过池领取与重新绑定。子孙记录继承只读磁盘引用，最后一个引用销毁后才回收文件，持久化和VM fork安全屏障未修改。','', '准备和资源成本（独立于请求计时）：',f'64槽准备 {prep["pool_64_startup_ms"]:.1f} ms；补槽实际工作中位数 {prep["refill_work_median_ms"]:.1f} ms；含1000ms等待的替补到位中位数 {prep["replacement_including_delay_median_ms"]:.1f} ms（{len(refill)}次补槽事件）。',f'镜像缓存首次创建+校验独立测量 {prep["cold_import"]["cold_cache_import_and_verification_ms"]:.1f} ms；已有缓存启动校验 {prep["slot_disk"]["cache_validation_ms"]:.1f} ms。缓存镜像2.5GiB，属于磁盘准备，不是memory.img。',f'静态helper上传 {prep["helper_upload"]["elapsed_ms"]:.2f} ms。空闲64槽的稀疏设备数据块实际分配0字节，各16GiB逻辑容量；镜像绑定后共享reflink extents，RAM继续CoW。池内VMM合计PSS约{pss/1024:.1f}MiB；FD范围{min(fdcounts)}..{max(fdcounts)}。','', '验证：',f'55项测试通过，无跳过；真实guest继承Python进程PID/nonce与16MiB状态，父内存改20、子改30，文件各自独立；采样共享物理页帧{val["shared_sampled_pfns"]}。', '父先销毁、子先销毁均通过；父销毁后从子继续派生孙沙箱，随后销毁子，孙仍可执行。', '最终fork及mlink清理审计通过，fork恢复64个ready槽，设备文件集合与活跃记录完全匹配，没有遗留已分配沙箱。', '没有memory.img；VMM/sandboxer二进制及基础镜像SHA256均与上一版相同。', '', '证据：baseline/、after/、prototype-*/原始每请求数据；stages.json、*-server.log、validation.json、tests.log、manifest.json、preparation.json、resources.json、changes.patch、source/。']
(R/'REPORT.txt').write_text('\n'.join(lines)+'\n');(R/'complete.json').write_text(json.dumps(dict(final_samples_per_product=10,baseline_samples_per_product=10,prototype_groups=3,validation=True,ready_pool=64),indent=2))
print(json.dumps(dict(helper=helper,preparation=prep,resources=resources),indent=2))
