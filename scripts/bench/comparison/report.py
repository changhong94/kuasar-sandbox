"""Regenerate machine-readable tables and SVG charts from saved raw results."""
import argparse
import csv
import html
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("directory")
args = p.parse_args()
root = Path(args.directory)
plan = json.loads((root / "plan.json").read_text())
groups = defaultdict(list)
batches = []


def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    x = (len(xs)-1)*q
    a = int(x)
    return xs[a] + (xs[min(a+1, len(xs)-1)]-xs[a])*(x-a)


def summarize(xs):
    return dict(n=len(xs), median=percentile(xs, .5), p95=percentile(xs, .95),
                minimum=min(xs) if xs else None, maximum=max(xs) if xs else None)


def io_delta(before, after):
    a = {r["pid"]: r for r in before["processes"] if r["scope"] == "platform"}
    total = dict(read_bytes=0, write_bytes=0, cpu_seconds=0)
    for r in after["processes"]:
        if r["scope"] != "platform" or r["pid"] not in a:
            continue
        for key in ("read_bytes", "write_bytes"):
            total[key] += max(0, r["io"].get(key, 0)-a[r["pid"]]["io"].get(key, 0))
        total["cpu_seconds"] += max(0, r["cpu_seconds"]-a[r["pid"]]["cpu_seconds"])
    return total


def cgroup_totals(stage):
    """Collapse observed ancestor/child paths; memory.stat file already includes shmem."""
    paths = sorted(stage["cgroups"], key=len)
    roots = []
    for path in paths:
        if not any(path == parent or path.startswith(parent.rstrip("/") + "/") for parent in roots):
            roots.append(path)
    if any(path in ("/", "/system.slice", "/user.slice") for path in roots):
        return None
    result = dict(current=0, anon=0, file=0, kernel=0)
    for path in roots:
        values = stage["cgroups"][path]
        result["current"] += int(values.get("memory.current", "0"))
        stats = dict(line.split() for line in values.get("memory.stat", "").splitlines())
        for key in ("anon", "file", "kernel"):
            result[key] += int(stats.get(key, 0))
    return {k: v/2**20 for k, v in result.items()}


for record in json.loads((root / "index.json").read_text()):
    if record["warmup"]:
        continue
    d = root / record["label"]
    r = json.loads((d / "results.json").read_text())
    stages = r["stages"]
    full = stages.get("steady", stages.get("after_full_touch"))
    before = stages["baseline"]
    if full is None:
        continue
    batch = dict(label=record["label"], product=r["product"], prefetch=r["prefetch"],
                 count=r["count"], cache=r["cache"], success=r.get("success", False),
                 ready_ms=[s["ready_ms"] for s in r["samples"] if s.get("verified")],
                 full_touch_ms=[s["full_touch_ms"] for s in r["samples"] if s.get("verified")],
                 nominal_mib=r["count"]*r["nominal_per_instance_mib"],
                 sandbox_pss_mib=full["totals_kib"]["sandbox"]["Pss"]/1024,
                 platform_pss_mib=full["totals_kib"]["platform"]["Pss"]/1024,
                 platform_pss_delta_mib=(full["totals_kib"]["platform"]["Pss"]-before["totals_kib"]["platform"]["Pss"])/1024,
                 sandbox_swap_mib=full["totals_kib"]["sandbox"]["Swap"]/1024,
                 available_mib=full["host_memory_kib"]["MemAvailable"]/1024,
                 platform_io_cpu_delta=io_delta(before, stages.get("after_full_touch", full)),
                 process_cpu_seconds=sum(s.get("cpu_seconds", 0) for s in stages.get("after_full_touch", full)["processes"] if s["scope"] == "sandbox"),
                 process_read_bytes=sum(s["io"].get("read_bytes", 0) for s in stages.get("after_full_touch", full)["processes"] if s["scope"] == "sandbox"),
                 before_touch_pss_mib=[s["before_touch"]["totals_kib"]["sandbox"]["Pss"]/1024 for s in r["samples"] if "before_touch" in s],
                 repeated_touch_ms=[x["elapsed_ms"] for rr in r.get("repeated_touch", []) for x in rr],
                 prefetch_started_lines=r.get("prefetch_started_lines"),
                 cold_advice=r.get("cold_advice"))
    batch["readonly_pss_mib"] = stages.get("after_full_touch", full)["totals_kib"]["sandbox"]["Pss"]/1024
    batch["mutated"] = bool(r.get("mutations"))
    batch["cgroup_memory_mib"] = cgroup_totals(full)
    batch["baseline_cgroup_memory_mib"] = cgroup_totals(before)
    endpoint = stages.get("after_full_touch", full)
    batch["cache_get_rpc_delta"] = None
    batch["cache_origin_hits_delta"] = None
    if "cache_info" in before and "cache_info" in endpoint:
        a, b = before["cache_info"], endpoint["cache_info"]
        batch["cache_get_rpc_delta"] = sum(b["server"][k]-a["server"][k] for k in ("hits", "misses"))
        batch["cache_origin_hits_delta"] = b["tiered"]["origin"]["hits"]-a["tiered"]["origin"]["hits"]
    if "storage_extents" in full:
        if r["product"] == "kuasar" and r.get("storage_scope") != "live" and not any(p.rstrip("/").endswith("/kuasar/runs") for p in r.get("storage_paths", [])):
            batch["storage_scope_note"] = "Legacy Store-only capture omitted live writable diffs; not a live-storage measurement."
        else:
            batch["storage_delta_mib"] = (full["storage_extents"]["unique_extent_bytes"]-before["storage_extents"]["unique_extent_bytes"])/2**20
    counters = {}
    log = d / "runner.jsonl"
    if log.exists():
        for line in log.read_text().splitlines():
            e = json.loads(line)
            match = re.fullmatch(r"\s*(source_read_calls|source_read_bytes|source_read_ns|fault_queue_wait_ns)\s+(\d+)\s*", str(e.get("MESSAGE", "")))
            if match:
                counters.setdefault(e.get("_SYSTEMD_UNIT", ""), {})[match[1]] = int(match[2])
    batch["runner_counters"] = {k: sum(v[k] for v in counters.values() if k in v)
                                for k in ("source_read_calls", "source_read_bytes", "source_read_ns", "fault_queue_wait_ns")} if counters else None
    batches.append(batch)
    groups[(r["product"], r["prefetch"], r["cache"], r["count"])].append(batch)

summary = []
for (product, prefetch, cache, count), bs in groups.items():
    item = dict(product=product, prefetch=prefetch, cache=cache, count=count, batches=len(bs),
                successful_batches=sum(b["success"] for b in bs))
    for key in ("ready_ms", "full_touch_ms", "before_touch_pss_mib", "repeated_touch_ms"):
        item[key] = summarize([v for b in bs for v in b[key]])
    for key in ("sandbox_pss_mib", "platform_pss_mib", "platform_pss_delta_mib",
                "process_cpu_seconds", "process_read_bytes", "available_mib", "sandbox_swap_mib", "readonly_pss_mib"):
        item[key] = summarize([b[key] for b in bs])
    item["source_read_mib"] = summarize([b["runner_counters"]["source_read_bytes"]/2**20 for b in bs if b["runner_counters"]])
    item["source_read_calls"] = summarize([b["runner_counters"]["source_read_calls"] for b in bs if b["runner_counters"]])
    item["storage_delta_mib"] = summarize([b["storage_delta_mib"] for b in bs if "storage_delta_mib" in b])
    for key in ("cache_get_rpc_delta", "cache_origin_hits_delta"):
        item[key] = summarize([b[key] for b in bs if b[key] is not None])
    item["observed_slo"] = {str(t): dict(
        ready_fraction=sum(x <= t for b in bs for x in b["ready_ms"])/(count*len(bs)),
        full_touch_fraction=sum(x <= t for b in bs for x in b["full_touch_ms"])/(count*len(bs)))
        for t in (500, 1000, 2000, 5000, 10000)}
    summary.append(item)
(root / "summary.json").write_text(json.dumps(dict(plan=plan, groups=summary, batches=batches), indent=2))
with (root / "summary.csv").open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["product", "prefetch", "cache", "count", "batches", "success_batches", "ready_p50_ms",
                     "ready_p95_ms", "full_touch_p50_ms", "full_touch_p95_ms", "sandbox_pss_mib", "platform_pss_mib", "logical_source_read_mib",
                     "readonly_pss_mib", "live_storage_delta_mib", "cache_get_rpc_delta"])
    for x in summary:
        writer.writerow([x["product"], x["prefetch"], x["cache"], x["count"], x["batches"], x["successful_batches"],
                         x["ready_ms"]["median"], x["ready_ms"]["p95"], x["full_touch_ms"]["median"],
                         x["full_touch_ms"]["p95"], x["sandbox_pss_mib"]["median"], x["platform_pss_mib"]["median"], x["source_read_mib"]["median"],
                         x["readonly_pss_mib"]["median"], x["storage_delta_mib"]["median"], x["cache_get_rpc_delta"]["median"]])

# Two aligned panels; diagnostic memory runs are not latency benchmarks.
is_memory = plan["stage"] == "memory"
keys = ("before_touch_pss_mib", "sandbox_pss_mib") if is_memory else ("ready_ms", "full_touch_ms")
titles = ("Before full touch: sandbox PSS (MiB)", "After full touch: sandbox PSS (MiB)") if is_memory else ("First simple command: median ms", "Full working-set verification: median ms")
h = 125 + len(summary)*43
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1250" height="{h+65}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial" fill="#222">',
       f'<text x="20" y="30" font-size="22">{html.escape(plan["stage"].title())} comparison — descriptive samples</text>']
for panel, (key, title) in enumerate(zip(keys, titles)):
    offset = panel*610
    svg.append(f'<text x="{offset+20}" y="65" font-size="17">{title}</text>')
    maximum = max((s[key]["median"] or 0) for s in summary) or 1
    for i, s in enumerate(summary):
        y = 100+i*43
        label = f'{s["product"]}/{s["prefetch"]} C{s["count"]} {s["cache"]}'
        value = s[key]["median"] or 0
        color = "#b40000" if s["product"] == "kuasar" else "#247ba0"
        svg.append(f'<text x="{offset+20}" y="{y}" font-size="11">{html.escape(label)}</text><rect x="{offset+315}" y="{y-14}" width="{value/maximum*220}" height="19" fill="{color}"/><text x="{offset+540}" y="{y}" font-size="12">{value:.1f}</text>')
svg.append(f'<text x="20" y="{h+15}" font-size="13">Same-host XFS loop; 2 vCPU / 2 GiB per instance; 256 MiB memory + 64 MiB file verified.</text>')
svg.append(f'<text x="20" y="{h+38}" font-size="13">File-advised-cold retains application/device caches. Small samples; p95 is descriptive, not an SLA guarantee.</text></g></svg>')
(root / "comparison.svg").write_text("".join(svg))
print(json.dumps(summary, indent=2))
