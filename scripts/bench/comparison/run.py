"""Run isolated product workers sequentially; concurrency exists only inside a batch."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--config", required=True)
p.add_argument("--output", required=True)
p.add_argument("--stage", choices=["memory", "cache", "density"], required=True)
p.add_argument("--repeats", type=int, default=3)
p.add_argument("--counts", default="1,2,4,8,12")
args = p.parse_args()
out = Path(args.output)
out.mkdir(parents=True, exist_ok=False)
(out / "plan.json").write_text(json.dumps(vars(args), indent=2))
worker = Path(__file__).with_name("worker.py")
config = json.loads(Path(args.config).read_text())
recorded_config = {k: config[k] for k in ("mount", "minimum_available_mib") if k in config}
recorded_config["products"] = {
    name: {k: product[k] for k in ("access", "fixture", "cold_paths", "extent_paths", "live_extent_paths", "binary_dir", "cache_health_endpoint") if k in product}
    for name, product in config["products"].items()
}
(out / "environment.json").write_text(json.dumps({
    "kernel": platform.release(), "python": sys.version,
    "sdk_versions": {name: importlib.metadata.version(name) for name in ("e2b", "httpx")},
    "cpuinfo": Path("/proc/cpuinfo").read_text(),
    "initial_meminfo": Path("/proc/meminfo").read_text(),
    "scripts_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in worker.parent.glob("*.py")},
    # This config stores paths and fixture identities; access-file credentials are not copied.
    "configuration": recorded_config,
}, indent=2))
records = []


def run(label, product, prefetch, count, cache="warm", extra=(), warmup=False):
    target = out / label
    cmd = [sys.executable, str(worker), "--config", args.config, "--product", product,
           "--output", str(target), "--prefetch", prefetch, "--count", str(count), "--cache", cache, *extra]
    print("START", label, flush=True)
    with (out / (label + ".log")).open("w") as f:
        q = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=600)
    r = json.loads((target / "results.json").read_text())
    record = dict(label=label, product=product, prefetch=prefetch, count=count, cache=cache,
                  warmup=warmup, success=r.get("success", False), exit_code=q.returncode)
    records.append(record)
    (out / "index.json").write_text(json.dumps(records, indent=2))
    print("DONE", label, "success", record["success"], flush=True)
    if r.get("cleanup_errors"):
        raise RuntimeError("Instance cleanup failed; inspect " + str(target))
    if q.returncode:
        print("STOP condition:", r.get("error", "worker failure; inspect sample errors"), flush=True)
        return False
    if product == "kuasar" and prefetch == "memory" and r.get("prefetch_started_lines", 0) != count:
        raise RuntimeError("Prefetch activation evidence incomplete: " + str(target))
    return True


variants = [("kuasar", "off"), ("kuasar", "memory"), ("cube", "off")]
if args.stage == "memory":
    for repeat in range(args.repeats):
        for product, mode in (variants if repeat % 2 == 0 else variants[::-1]):
            if not run(f"r{repeat}-{product}-{mode}", product, mode, 1,
                       extra=["--memory-stages", "--hold-seconds", "3"]):
                raise SystemExit(1)
elif args.stage == "cache":
    for repeat in range(args.repeats):
        for product, mode in (variants if repeat % 2 == 0 else variants[::-1]):
            for count in (1, 4):
                # A full-touch restore warms the selected snapshot's working set.
                if not run(f"r{repeat}-{product}-{mode}-c{count}-warmup", product, mode, count, warmup=True):
                    raise SystemExit(1)
                for cache in (("warm", "file-advised-cold") if repeat % 2 == 0 else ("file-advised-cold", "warm")):
                    if not run(f"r{repeat}-{product}-{mode}-c{count}-{cache}", product, mode, count, cache):
                        raise SystemExit(1)
elif args.stage == "density":
    # Fixed workload and several reporting thresholds, not a claimed universal maximum density.
    for product, mode in variants:
        for count in map(int, args.counts.split(",")):
            for repeat in range(args.repeats):
                if not run(f"r{repeat}-{product}-{mode}-n{count}", product, mode, count,
                           extra=["--hold-seconds", "3", "--repeat-touch", "3", "--storage", "--mutate"]):
                    # Preserve failed admission/overload as capacity evidence, stop increasing this variant.
                    break
            else:
                continue
            break
print("COMPLETE", out, flush=True)
