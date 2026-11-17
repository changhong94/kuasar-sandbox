import pathlib,json,re,statistics,hashlib,shutil,difflib
R=pathlib.Path('/opt/bench108/results/beat-mlink-108');M=pathlib.Path('/opt/bench108');K=M/'src/kuasar-fork/kuasar-io/kuasar';CH=M/'src/kuasar-fork/cloud-hypervisor/cloud-hypervisor'
def stats(a):return dict(n=len(a),median_ms=statistics.median(a),max_ms=max(a))
summary={}
for run in ['network-v1','native-tcp','speed','poll','generic','demand','overlap']:
 rows=[json.loads(p.read_text()) for p in (R/run).glob('*-kuasar-fork.json')];ids={d['sandbox_id'] for d in rows}
 base=json.loads((R/run/'summary.json').read_text());ph={};st={};guest={}
 for line in (R/(run+'.log')).read_text().splitlines():
  if line.startswith('E2B_TIMING '):
   d=json.loads(line[11:])
   if d.get('sid') not in ids:continue
   st.setdefault(d['stage'],[]).append(d['elapsed_ms'])
   if d['stage']=='snapshot_bind':
    for x in d['details']['phases']:ph.setdefault(x['phase'],[]).append(x['ms'])
   if d['stage']=='image_mount':
    for k,v in json.loads(d['helper']).items():
     if isinstance(v,(int,float)):ph.setdefault('mount_helper.'+k,[]).append(v/1000)
  m=re.search(r'FORK_GUEST_PHASE (\S+) (\[.*\])',line)
  if m and m[1] in ids and any(k=='tcp_reset' for k,v in json.loads(m[2])):guest[m[1]]=dict(json.loads(m[2]))
 item=dict(comparison=base,phases={k:stats(v) for k,v in ph.items()},stages={k:stats(v) for k,v in st.items()},first_command=stats([d['ready_ms']-d['api_ms'] for d in rows]),all_success_destroyed=all(d['success'] and d['destroyed'] and d['attempts']==1 for d in rows))
 if guest:item['guest_phases']={k:stats([v[k]/1000 for v in guest.values()]) for k in next(iter(guest.values()))}
 summary[run]=item
entry=summary['overlap'];ids={json.loads(p.read_text())['sandbox_id'] for p in (R/'overlap').glob('*-kuasar-fork.json')}
e=[json.loads(l) for l in (R/'overlap-pool-events.jsonl').read_text().splitlines()];ref=[d for d in e if d.get('retired_sid') in ids];entry['refill']={k:stats([d[k] for d in ref]) for k in ['elapsed_ms','replacement_ms']}
j=[json.loads(l) for l in (R/'overlap-journal.jsonl').read_text().splitlines()];start=int((R/'overlap-start-us.txt').read_text());listen=[d for d in j if 'E2B compatible API listening' in str(d.get('MESSAGE',''))][-1];entry['service_startup_ms']=(int(listen['__MONOTONIC_TIMESTAMP'])-start)/1000
entry['preparation']=json.loads((R/'overlap-preparation.json').read_text());entry['resources']={k:json.loads((R/('overlap-resources-'+k+'.json')).read_text())['totals'] for k in ['before','after']}
(R/'measurements.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(entry,indent=2))
