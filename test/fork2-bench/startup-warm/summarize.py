import pathlib,json,statistics,csv,math
r=pathlib.Path(__file__).parent;s=r/'results/startup';out={};historical={'python':(38.1853105,66.405929,96.52),'node':(37.2756295,98.1736535,179.69),'ruby':(38.092072,130.092532,167.31)}
for l in ['python','node','ruby']:
 out[l]={}
 for p in ['fork2','old','mlink']:
  rows=[json.load(open(s/f'{l}-{p}-{i:02d}.json')) for i in range(1,51)];assert all(x['success'] and x['destroyed'] for x in rows)
  out[l][p]={'n':50,**{k:dict(median=statistics.median(a:=sorted(x[k] for x in rows)),p95=a[47],p99=a[49],maximum=a[-1]) for k in ['api_ms','ready_ms','print_ms','interpreter_ms']}}
(r/'summary.json').write_text(json.dumps(out,indent=2))
lines=['# 113：旧报告热路径基线复现','', '三方 × Python/Node.js/Ruby；每组 1 次 warmup + 50 次串行正式测试。固定镜像 digest、相同命令、2 vCPU / 2 GiB、64 个通用预备槽，8 路准备。', '', '新旧 fork 使用持久化磁盘，模板准备采用旧报告的通用 512 MiB 普通文件预读上限；没有语言白名单，没有提前执行解释器，没有每镜像 VM 池。mlink 沿用原生 full-warm 模板缓存/L2 通用池，其缓存实现不等同于 fork。', '', '每次新旧 fork 请求前校验目标持久化载体宿主页缓存 100% 驻留，不足时读入；此步骤在计时外并逐次记录。旧报告每次都读取全部文件，本次已全部驻留的文件不重复读取，保持相同驻留状态。', '', 'Ready：创建调用开始至客户端收到 shell 标识；print：同一起点至客户端收到解释器随机标识，包含解释器启动。', '', '| 语言 | 产品 | Ready 中位 | Ready P95 | Ready P99/最大 | print 中位 | print P95 | print P99/最大 |','|---|---|---:|---:|---:|---:|---:|---:|']
for l,ps in out.items():
 for p,a in ps.items():
  b=a['ready_ms'];c=a['print_ms'];lines.append(f"| {l} | {p} | {b['median']:.2f} | {b['p95']:.2f} | {b['maximum']:.2f} | {c['median']:.2f} | {c['p95']:.2f} | {c['maximum']:.2f} |")
lines+=['','单位 ms。nearest-rank P99 在 50 个样本下等于最大值。','','## 旧报告与本次旧 fork','', '| 语言 | 旧报告 print | 本次旧 fork print | 变化 |','|---|---:|---:|---:|']
for l,(_,old,_) in historical.items():
 v=out[l]['old']['print_ms']['median'];lines.append(f'| {l} | {old:.2f} | {v:.2f} | {(v/old-1)*100:+.1f}% |')
lines+=['','## 缓存差异对照','', '上一轮新旧 fork 均把通用文件预读设为 0；旧报告为 536870912 字节。仅补齐宿主页缓存的 Node.js 诊断对照（1 次 warmup + 10 次测量）仍约 210.57 ms，未恢复旧报告性能；说明不能只用宿主页缓存解释差距。', '', '| 模板准备 | fork2 实际读入 MiB | fork2 准备总耗时 ms | 旧 fork 实际读入 MiB | 旧 fork 模板制作 ms |','|---|---:|---:|---:|---:|']
p=json.load(open(r/'results/template-preparation.json'))
for l in historical:
 a=p['new'][l];b=p['old'][{'python':'base','node':'node','ruby':'ruby'}[l]]
 lines.append(f"| {l} | {a['cache']['regular_file_bytes_read']/2**20:.2f} | {a['costs_ms']['total_preparation']:.2f} | {b['metadata_cache']['regular_file_bytes_read']/2**20:.2f} | {b['preparation_ms']:.2f} |")
lines+=['','模板费用计时范围遵循各实现的准备日志，不用于直接计算准备速度比例；不含已有镜像下载和导入。读取量不同是各镜像挂载树包含的运行时文件不同，三种镜像均未触及 512 MiB 上限。','', '原始逐请求数据：results/startup/；诊断对照：results/pilot-host-only/；独立写入与删除：results/validation-*.json；清理：results/cleanup-audit.json。']
(r/'README.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
with (r/'samples.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['language','product','iteration','api_ms','ready_ms','print_ms','interpreter_ms'])
 for l in out:
  for p in out[l]:
   for i in range(1,51):
    d=json.load(open(s/f'{l}-{p}-{i:02d}.json'));w.writerow([l,p,i]+[d[k] for k in ['api_ms','ready_ms','print_ms','interpreter_ms']])
