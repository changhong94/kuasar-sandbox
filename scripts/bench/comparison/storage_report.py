"""Summarize prepare.py storage output using extent accounting, not global df."""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("directory")
args = p.parse_args()
root = Path(args.directory)
groups = defaultdict(list)
raw = []
for entry in json.loads((root/"index.json").read_text()):
    d = root/entry["case"]
    c = json.loads((d/"case.json").read_text())
    r = json.loads((d/entry["product"]/"results.json").read_text())
    if not r.get("success") or not all(v.get("memory_verified") and v.get("restore_verified") for v in r["versions"]):
        raise SystemExit("Incomplete or failed case: "+str(d))
    m = r["measurements"]
    def size(label):
        return statistics.mean(s["unique_extent_bytes"] for s in m[label]["extent_samples"])
    baseline = size("baseline")
    row = dict(case=entry["case"], product=entry["product"], entropy=c["entropy"], mode=c["mode"],
               cumulative_mib=[(size("retained_"+str(i))-baseline)/2**20 for i in range(1,c["instances"]+1)],
               maximum_scan_drift_mib=max(abs(v["extent_samples"][0]["unique_extent_bytes"]-v["extent_samples"][1]["unique_extent_bytes"])/2**20 for v in m.values()),
               file_hashes=[v["sha256"] for v in r["versions"]],
               memory_hashes=[v["memory_baseline"]["sha256"] for v in r["versions"]])
    raw.append(row)
    groups[(c["entropy"],c["mode"],entry["product"])].append(row["cumulative_mib"][-1])
for case in {x["case"] for x in raw}:
    pair=[x for x in raw if x["case"]==case]
    assert len(pair)==2 and pair[0]["file_hashes"]==pair[1]["file_hashes"] and pair[0]["memory_hashes"]==pair[1]["memory_hashes"]
summary=[dict(entropy=k[0],mode=k[1],product=k[2],rounds=len(v),mean_mib=statistics.mean(v),min_mib=min(v),max_mib=max(v)) for k,v in groups.items()]
(root/"summary.json").write_text(json.dumps(dict(groups=summary,raw=raw),indent=2))
maximum=max(x["mean_mib"] for x in summary)
height=150+len(summary)*50
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial"><text x="25" y="40" font-size="24">Retained snapshot data: physical extent union</text>']
for i,s in enumerate(summary):
    y=85+i*50
    color="#b40000" if s["product"]=="kuasar" else "#247ba0"
    svg.append(f'<text x="25" y="{y}" font-size="15">{s["entropy"]}/{s["mode"]}/{s["product"]}</text><rect x="300" y="{y-18}" width="{s["mean_mib"]/maximum*500}" height="23" fill="{color}"/><text x="820" y="{y}" font-size="15">{s["mean_mib"]:.1f} MiB</text>')
svg.append(f'<text x="25" y="{height-35}" font-size="14">Cache and filesystem metadata excluded; shared extents counted once. See raw scan drift.</text></g></svg>')
(root/"comparison.svg").write_text("".join(svg))
print(json.dumps(summary,indent=2))
