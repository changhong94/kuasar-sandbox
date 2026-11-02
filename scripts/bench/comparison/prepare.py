"""Prepare portable config and verified snapshot fixtures; no product deployment changes."""
import argparse
import hashlib
import json
import os
import platform
import secrets
import subprocess
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="command", required=True)
init = sub.add_parser("config")
init.add_argument("--kuasar-access", required=True)
init.add_argument("--cube-access", required=True)
init.add_argument("--mount", required=True)
init.add_argument("--output", required=True)
for name in ("fixtures", "storage"):
    q = sub.add_parser(name)
    q.add_argument("--config", required=True)
    q.add_argument("--output", required=True)
    q.add_argument("--seed", type=int, default=None)
    if name == "storage":
        q.add_argument("--repeats", type=int, default=2)
        q.add_argument("--instances", type=int, default=3)
args = p.parse_args()
if args.command == "config":
    mount = Path(args.mount).resolve()
    k = json.loads(Path(args.kuasar_access).read_text())
    cfg = dict(mount=str(mount), minimum_available_mib=4096, products={
        "kuasar": dict(access=str(Path(args.kuasar_access).resolve()), binary_dir=k["bin"],
                       extent_paths=[str(mount/"kuasar/store")],
                       live_extent_paths=[str(mount/"kuasar/store"),str(mount/"kuasar/runs")],
                       cold_paths=[str(mount/"kuasar/store"), str(mount/"kuasar/cache-rocks")]),
        "cube": dict(access=str(Path(args.cube_access).resolve()), binary_dir="/usr/local/services/cubetoolbox",
                     extent_paths=[str(mount/"cubesandbox"), str(mount/"cubesandbox-extra")],
                     live_extent_paths=[str(mount/"cubesandbox"), str(mount/"cubesandbox-extra")],
                     cold_paths=[str(mount/"cubesandbox"), str(mount/"cubesandbox-extra")])})
    target = Path(args.output)
    if target.exists():
        raise SystemExit("Refusing to overwrite existing config")
    target.write_text(json.dumps(cfg, indent=2))
    raise SystemExit(0)

cfg_path = Path(args.config)
cfg = json.loads(cfg_path.read_text())
out = Path(args.output)
out.mkdir(parents=True, exist_ok=False)
seed = args.seed if args.seed is not None else secrets.randbits(48)
environment = dict(arguments=vars(args), seed=seed, kernel=platform.release(), machine=platform.machine(),
                   python=sys.version, cpu=Path("/proc/cpuinfo").read_text(),
                   memory=Path("/proc/meminfo").read_text(),
                   mount=subprocess.check_output(["findmnt", "-J", cfg["mount"]], text=True),
                   binaries={})
for binary in Path(cfg["products"]["kuasar"]["binary_dir"]).iterdir():
    if binary.is_file():
        h = hashlib.sha256()
        with binary.open("rb") as f:
            for block in iter(lambda: f.read(1024*1024), b""):
                h.update(block)
        environment["binaries"][binary.name] = h.hexdigest()
(out/"environment.json").write_text(json.dumps(environment, indent=2))
cases = [(0, "high", "same")] if args.command == "fixtures" else [
    (repeat, entropy, mode) for repeat in range(args.repeats)
    for entropy in ("low", "high") for mode in ("same", "different")]
records = []
for i, (repeat, entropy, mode) in enumerate(cases):
    d = out/f"{entropy}-{mode}-r{repeat}"
    d.mkdir()
    (d/"case.json").write_text(json.dumps(dict(seed=seed+i*1000, run=repeat, entropy=entropy, mode=mode,
                                               instances=1 if args.command=="fixtures" else args.instances)))
    for product in (("kuasar", "cube") if repeat%2 else ("cube", "kuasar")):
        with (d/(product+".log")).open("w") as f:
            q = subprocess.run([sys.executable, str(Path(__file__).with_name("fixture_worker.py")),
                                product, str(d), str(cfg_path)], stdout=f, stderr=subprocess.STDOUT, timeout=900)
        r = json.loads((d/product/"results.json").read_text())
        records.append(dict(case=d.name, product=product, success=r.get("success")))
        (out/"index.json").write_text(json.dumps(records, indent=2))
        if q.returncode or not r.get("success") or r.get("delete_errors"):
            raise SystemExit("Fixture/storage run failed; see "+str(d))
        if args.command == "fixtures":
            cfg["products"][product]["fixture"] = r["versions"][0]
        print("DONE", d.name, product, flush=True)
if args.command == "fixtures":
    # Update only after both products passed full restore verification.
    cfg_path.write_text(json.dumps(cfg, indent=2))
    print("Verified fixture references saved to", cfg_path)
