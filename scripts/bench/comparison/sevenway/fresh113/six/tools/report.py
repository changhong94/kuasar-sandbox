from pathlib import Path
import json,statistics,csv
B=Path('/home/hong/src/research/sevenway-current-20261126/six');R=B/'results';M=R/'matrix'
products=['kuasar-off','kuasar-uffd','cube','agentenv','kuasar-mlink','kuasar-fork'];langs=['python','node','ruby']
a=json.loads((R/'final-audit.json').read_text());assert a['passed']
rows=[];prep=[];lines=['113 six-product startup benchmark','Protocol: 2 vCPU / 2048 MiB; 1 disposable warmup + 50 serial measured requests per product/language; rotated product order.', 'Clock: immediately before SDK/CLI create until client receives random interpreter print line; fresh interpreter start included. No retries/trimming. P95/P99 use nearest rank (n=50 => P99=max).', 'No language-specific training. Fork performs bounded generic image-file cache preparation, not cold-cache startup. Template preparation never executes the interpreter. Identity preflight and warmup guests are destroyed, never recaptured.', 'Pool capacity: 2 for configurable fork and mlink pools; selected mlink image storage target 2. Separate language image artifacts, one shared fork VM pool.', 'Only owned fork/mlink benchmark services changed; other users processes left untouched.', 'Preparation uses existing pinned OCI assets: download/copy from scratch is not included in template timings. Failed deployment attempts retained in preparation.jsonl.', '', 'REQUEST TO PRINT (ms): language product median P95 P99 max']
for l in langs:
 summary=json.loads((M/l/'summary.json').read_text())
 for n in products:
  d=summary[n];rows.append(dict(language=l,product=n,**d));lines.append(f"{l} {n}: {d['median_ms']:.3f} {d['p95_ms']:.3f} {d['p99_ms']:.3f} {d['max_ms']:.3f}")
lines+=['','PREPARATION (ms, one observed build per template; not a distribution):']
f=json.loads((R/'fork-preparation.json').read_text())
for l in langs:
 for n in products:
  if n=='kuasar-fork':
   d=f['image_templates']['base' if l=='python' else l];p=dict(language=l,product=n,template_ms=d['preparation_ms'],host_ram_warm_ms=d['warmup_ms'],generic_file_cache_ms=d['metadata_cache']['rpc_elapsed_ms'],file_bytes_read=d['metadata_cache']['regular_file_bytes_read'])
  else:
   d=json.loads((R/f'template-{n}-{l}.json').read_text());p=dict(language=l,product=n,template_ms=d['elapsed_ms'],prewarm_ms=d.get('prewarm_ms'))
  prep.append(p);lines.append(json.dumps(p))
lines += [f"Fork service start to ready (all 3 image templates): {f['service_start_to_ready_ms']:.3f} ms; initial 2-slot preparation {f['pool']['preparation_ms']:.3f} ms.",'Generic file-cache and RAM-warm substage costs may be nested in template preparation: do not sum as independent totals.','MLink per-language policy switches are separately recorded under matrix/preparation/*/policy-preparation.json.','','POST-REQUEST REFILL WAIT (ms median; polling includes cleanup/readiness, not pure internal refill):']
for l in langs:
 for n in ['kuasar-fork','kuasar-mlink']:
  samples=[json.loads((M/l/f'{i:02d}-{n}.json').read_text()) for i in range(1,51)]
  lines.append(f"{l} {n}: {statistics.median(x['pool_after']['elapsed_ms'] for x in samples):.3f}")
lines+=['','Validation: 900/900 measured requests and 18 warmups succeeded on first attempt. All samples deleted. For every product/language, two simultaneous sandboxes held distinct file contents; both destruction orders tested and survivor executed a fresh interpreter successfully. Final native inventories have no assigned test sandboxes; reusable pool slots remain.','', 'DIGESTS:']
c=json.loads((B/'tools/config.json').read_text())
for l in langs:lines.append(l+' '+c['_languages'][l]['digest'])
loads=[]
for p in M.glob('*/round*-host.json'):loads.append(float(json.loads(p.read_text())['loadavg'].split()[0]))
lines.append(f'Host 1-minute load observed at sample boundaries: min={min(loads):.2f}, median={statistics.median(loads):.2f}, max={max(loads):.2f}.')
(R/'report.txt').write_text('\n'.join(lines)+'\n');(R/'summary.json').write_text(json.dumps({'startup':rows,'preparation':prep,'validation':a},indent=2))
with (R/'startup-summary.csv').open('w') as o:
 w=csv.DictWriter(o,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('\n'.join(lines))
