"""One product per process: e2b reads endpoint environment at import time."""
import argparse
import concurrent.futures
import fcntl
import json
import os
import subprocess
import time
import traceback
import uuid
from pathlib import Path
from measure import capture, processes, advise_cold

p = argparse.ArgumentParser()
p.add_argument("--config", required=True)
p.add_argument("--product", choices=["kuasar", "cube"], required=True)
p.add_argument("--output", required=True)
p.add_argument("--prefetch", choices=["off", "memory"], default="off")
p.add_argument("--cache", choices=["warm", "file-advised-cold"], default="warm")
p.add_argument("--count", type=int, default=1)
p.add_argument("--memory-stages", action="store_true")
p.add_argument("--hold-seconds", type=float, default=0)
p.add_argument("--repeat-touch", type=int, default=0)
p.add_argument("--storage", action="store_true")
p.add_argument("--mutate", action="store_true")
args = p.parse_args()
cfg = json.loads(Path(args.config).read_text())
mount_root = Path(cfg["mount"]).resolve()
if mount_root == Path("/"):
    raise SystemExit("Comparison mount must not be the filesystem root")
for field in ("cold_paths", "extent_paths", "live_extent_paths"):
    for path in cfg["products"][args.product].get(field, []):
        resolved = Path(path).resolve()
        if resolved == mount_root or not resolved.is_relative_to(mount_root):
            raise SystemExit("Measurement paths must be subdirectories of the comparison mount")
c = json.loads(Path(cfg["products"][args.product]["access"]).read_text())
fixture = cfg["products"][args.product]["fixture"]
out = Path(args.output)
out.mkdir(parents=True, exist_ok=False)
os.environ.update(E2B_API_KEY=c["api_key"], E2B_DOMAIN=c["domain"], SSL_CERT_FILE=c["ca_file"], NO_PROXY="*")
os.environ.pop("E2B_API_URL", None)
if args.product == "cube":
    os.environ["E2B_API_URL"] = c["api_url"]
from e2b import Sandbox

instances = []
marker = " # comparison-suite-" + uuid.uuid4().hex
rows = []
memory_expected = {}
result = dict(product=args.product, count=args.count, prefetch=args.prefetch, cache=args.cache,
              nominal_per_instance_mib=2048, samples=rows, started_at=time.time(), stages={})


def save():
    (out / "results.json").write_text(json.dumps(result, indent=2))


def hosts(add=None):
    with open("/run/comparison-hosts.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = Path("/etc/hosts")
        if add:
            with path.open("a") as f:
                f.write("\n127.0.0.2 " + add + marker + "\n")
        else:
            path.write_text("".join(l for l in path.read_text().splitlines(True) if marker not in l))


def platform_pids():
    table = processes()
    roots = []
    for pid, v in table.items():
        # Match executable token, never a shell command containing a path.
        exe = v["cmd"].split(" ")[0]
        if args.product == "kuasar":
            if exe.startswith(cfg["products"]["kuasar"]["binary_dir"] + "/"):
                roots.append(pid)
        elif exe.startswith("/usr/local/services/cubetoolbox/"):
            roots.append(pid)
    if args.product == "cube":
        names = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}"], text=True).splitlines()
        names = [n for n in names if n.startswith("cube-")]
        if names:
            roots += [int(x) for x in subprocess.check_output(
                ["docker", "inspect", "--format", "{{.State.Pid}}", *names], text=True).split()]
    return roots


def snapshot(stage):
    result["stages"][stage] = capture([s.sandbox_id for s in instances], platform_pids())
    if args.product == "kuasar":
        env = dict(os.environ, LD_LIBRARY_PATH=str(Path(c["bin"]).parent/"lib"))
        q = subprocess.run([str(Path(c["bin"])/"cache-ctl"), "info", "--json", "--endpoint",
                            cfg["products"]["kuasar"].get("cache_health_endpoint",
                                "unix://"+cfg["mount"]+"/kuasar/run/cache-health.sock")],
                           env=env, text=True, capture_output=True, timeout=15)
        if q.returncode == 0:
            result["stages"][stage]["cache_info"] = json.loads(q.stdout)
        else:
            result["stages"][stage]["cache_info_error"] = q.stderr
    if args.storage:
        from extent_accounting import scan
        paths = cfg["products"][args.product].get("live_extent_paths", cfg["products"][args.product]["extent_paths"])
        result["storage_paths"] = paths
        result["storage_scope"] = "live" if "live_extent_paths" in cfg["products"][args.product] else "retained"
        result["stages"][stage]["storage_extents"] = scan(paths)
    save()


probe = "python3 -c 'import urllib.request;print(urllib.request.urlopen(\"http://127.0.0.1:8002/\").read().decode())'"


def touch(s):
    memory = json.loads(s.commands.run(probe, timeout=90).stdout)
    digest = s.commands.run("sha256sum /home/user/history.bin", timeout=90).stdout.split()[0]
    assert memory["sha256"] == memory_expected.get(s.sandbox_id, fixture["memory_baseline"]["sha256"]), "memory hash mismatch"
    assert memory["instance"] == fixture["memory_baseline"]["instance"], "memory process restarted"
    assert digest == fixture["sha256"], "file hash mismatch"
    return True


def start_one(index):
    row = dict(index=index, start_ns=time.monotonic_ns())
    rows.append(row)
    t = time.perf_counter()
    kw = {}
    if args.product == "kuasar":
        kw["metadata"] = {"kuasar-sandbox.restore": json.dumps({"prefetch": args.prefetch})}
    try:
        s = Sandbox.create(fixture["template"], timeout=900, **kw)
        instances.append(s)
        row["sid"] = s.sandbox_id
        row["api_ms"] = (time.perf_counter() - t) * 1000
        if args.product == "kuasar":
            hosts(s.get_host(49983))
        assert s.commands.run("printf READY", timeout=90).stdout == "READY"
        row["ready_ms"] = (time.perf_counter() - t) * 1000
        if args.memory_stages:
            # Diagnostic run only: sampling overhead must not enter timed full-touch comparisons.
            row["before_touch"] = capture([s.sandbox_id], [])
        touch(s)
        row["full_touch_ms"] = (time.perf_counter() - t) * 1000
        row["process_stats"] = capture([s.sandbox_id], [])
        row["verified"] = True
    except Exception:
        row["error"] = traceback.format_exc()
    row["end_ns"] = time.monotonic_ns()
    return row


try:
    snapshot("baseline")
    if result["stages"]["baseline"]["host_memory_kib"]["MemAvailable"] < cfg.get("minimum_available_mib", 4096) * 1024:
        raise RuntimeError("Available host memory below configured safety floor")
    if args.cache == "file-advised-cold":
        subprocess.run(["sync", "-f", cfg["mount"]], check=True)
        result["cold_advice"] = advise_cold(cfg["products"][args.product]["cold_paths"])
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.count) as executor:
        list(executor.map(start_one, range(args.count)))
    snapshot("after_full_touch")
    if args.mutate:
        def mutate(pair):
            index, s = pair
            seed = 1000 + index
            cmd = "python3 -c 'import urllib.request;print(urllib.request.urlopen(urllib.request.Request(\"http://127.0.0.1:8002/?seed=" + str(seed) + "\",data=b\"\",method=\"POST\")).read().decode())'"
            response = json.loads(s.commands.run(cmd, timeout=90).stdout)
            assert response["instance"] == fixture["memory_baseline"]["instance"]
            assert response["sha256"] != fixture["memory_baseline"]["sha256"]
            memory_expected[s.sandbox_id] = response["sha256"]
            # Extra disk data is per-instance and reproducible, independent of template contents.
            code = "import random,os,hashlib; b=random.Random(" + str(seed) + ").randbytes(64*1024*1024); f=open(\"/home/user/density-dirty.bin\",\"wb\"); f.write(b); f.flush(); os.fsync(f.fileno()); f.close(); print(hashlib.sha256(b).hexdigest())"
            import shlex
            digest = s.commands.run("python3 -c " + shlex.quote(code), timeout=90).stdout.strip()
            check = s.commands.run("sha256sum /home/user/density-dirty.bin", timeout=90).stdout.split()[0]
            assert digest == check
            return dict(sid=s.sandbox_id, memory_sha256=response["sha256"], disk_sha256=digest, seed=seed)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.count) as executor:
            result["mutations"] = list(executor.map(mutate, enumerate(instances)))
        assert len(set(memory_expected.values())) == len(instances)
        snapshot("after_mutation")
    result["repeated_touch"] = []
    for iteration in range(args.repeat_touch):
        def timed_touch(s):
            t = time.perf_counter()
            touch(s)
            return dict(sid=s.sandbox_id, elapsed_ms=(time.perf_counter()-t)*1000)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.count) as executor:
            result["repeated_touch"].append(list(executor.map(timed_touch, instances)))
    if args.hold_seconds:
        time.sleep(args.hold_seconds)
        snapshot("steady")
    result["success"] = all(r.get("verified") for r in rows) and len(rows) == args.count
except Exception:
    result["success"] = False
    result["error"] = traceback.format_exc()
finally:
    result["cleanup_errors"] = []
    for s in instances:
        try:
            s.kill()
        except Exception as e:
            result["cleanup_errors"].append(str(e))
    if args.product == "kuasar":
        hosts()
    # Runner termination flushes logical source read counters.
    time.sleep(2)
    if args.product == "kuasar":
        journal = subprocess.run(["journalctl", "--since", "@" + str(int(result["started_at"])),
                                  "--no-pager", "-o", "json"], capture_output=True, text=True, timeout=45)
        ids = [r.get("sid", "") for r in rows if r.get("sid")]
        entries = []
        for line in journal.stdout.splitlines():
            try:
                e = json.loads(line)
                entries.append(e)
            except ValueError:
                pass
        run_ids = set()
        import re
        for e in entries:
            msg = str(e.get("MESSAGE", ""))
            if any(sid in msg for sid in ids):
                for run in re.findall(r"run_id=(sr-[0-9a-f-]+)", msg):
                    run_ids.add(run)
        units = {e.get("_SYSTEMD_UNIT") for e in entries
                 if any(str(e.get("_SYSTEMD_UNIT", "")).endswith("@" + run + ".service") for run in run_ids)}
        units |= {e.get("_SYSTEMD_UNIT") for e in entries if e.get("KUASAR_SANDBOX_ID") in ids and e.get("_SYSTEMD_UNIT")}
        selected = [e for e in entries if e.get("_SYSTEMD_UNIT") in units or any(sid in str(e.get("MESSAGE", "")) for sid in ids)]
        (out / "runner.jsonl").write_text("\n".join(json.dumps(e) for e in selected))
        result["runner_units"] = sorted(units)
        result["prefetch_started_lines"] = sum("memory prefetch started" in str(e.get("MESSAGE", "")) for e in selected)
        conductor_log = Path(c["work_dir"]) / "orch.log"
        if conductor_log.exists():
            phase_lines = [line for line in conductor_log.read_text().splitlines()
                           if ("sandbox launch phase" in line or "sandbox launch terminal" in line)
                           and any("sid="+sid+" " in line for sid in ids)]
            (out/"conductor-phases.log").write_text("\n".join(phase_lines))
    snapshot("after_delete")
    if result["stages"]["after_delete"]["totals_kib"]["sandbox"]["Pss"]:
        time.sleep(5)
        snapshot("after_delete_retry")
        if result["stages"]["after_delete_retry"]["totals_kib"]["sandbox"]["Pss"]:
            result["cleanup_errors"].append("Matching sandbox processes remain after deletion; inspect process records")
    instances.clear()
    save()
print(json.dumps({k: result.get(k) for k in ("product", "count", "cache", "prefetch", "success", "error")}), flush=True)
if not result.get("success") or result["cleanup_errors"]:
    raise SystemExit(1)
