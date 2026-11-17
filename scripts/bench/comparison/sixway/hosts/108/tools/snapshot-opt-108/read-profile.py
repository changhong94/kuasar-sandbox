import pathlib,json
R=pathlib.Path('/opt/bench108/results/snapshot-opt-108');ids={x['sid'] for x in json.loads((R/'diagnostic.json').read_text())};out=[]
for l in (R/'profile.log').read_text().splitlines():
 if not l.startswith('E2B_TIMING '):continue
 d=json.loads(l[11:])
 if d['stage']!='snapshot_bind' or d['sid'] not in ids:continue
 detail=d['details'];prev=detail['initial_process'];rows=[]
 for x in detail['phases']:
  now=x['process'];old={t['tid']:t['cpu_ns'] or 0 for t in prev['threads']};delta={}
  for t in now['threads']:delta[t['name']]=delta.get(t['name'],0)+((t['cpu_ns'] or 0)-old.get(t['tid'],0))/1e6
  rows.append(dict(phase=x['phase'],wall_ms=round(x['ms'],3),cpu_ms=round(sum(delta.values()),3),threads=delta,minor=now['minor_faults']-prev['minor_faults'],major=now['major_faults']-prev['major_faults']));prev=now
 out.append(dict(sid=d['sid'],phases=rows));print(d['sid']);print('\n'.join(str({k:v for k,v in x.items() if k!='threads'}) for x in rows))
(R/'profile.json').write_text(json.dumps(out,indent=2))
