"""Linux-only measurement helpers. Never reads process environments or secrets."""
import os
import json
import time
import stat
from pathlib import Path


def fields(text):
    result = {}
    for line in text.splitlines():
        parts = line.replace(":", "").split()
        if len(parts) >= 2:
            try:
                result[parts[0]] = int(parts[1])
            except ValueError:
                pass
    return result


def processes():
    result = {}
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            raw = (p / "stat").read_text().rsplit(")", 1)[1].split()
            result[int(p.name)] = {
                "ppid": int(raw[1]),
                "cpu_seconds": (int(raw[11]) + int(raw[12])) / os.sysconf("SC_CLK_TCK"),
                "cmd": (p / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace"),
            }
        except OSError:
            continue
    return result


def descendants(table, roots):
    selected = set(roots)
    while True:
        more = {pid for pid, v in table.items() if v["ppid"] in selected}
        if more <= selected:
            return selected
        selected |= more


def capture(sids, platform_roots=()):
    table = processes()
    own = descendants(table, [p for p, v in table.items() if any(sid in v["cmd"] for sid in sids)])
    platform = descendants(table, [p for p in platform_roots if p in table]) - own
    rows = []
    groups = {}
    for pid in sorted(own | platform):
        p = Path("/proc") / str(pid)
        try:
            memory = fields((p / "smaps_rollup").read_text())
            cg = (p / "cgroup").read_text().strip().split("::")[-1]
            base = Path("/sys/fs/cgroup") / cg.lstrip("/")
            if cg not in groups:
                groups[cg] = {
                    name: (base / name).read_text()
                    for name in ("memory.current", "memory.stat", "memory.events", "cpu.stat", "io.stat")
                    if (base / name).exists()
                }
            rows.append(dict(pid=pid, scope="sandbox" if pid in own else "platform",
                             cpu_seconds=table[pid]["cpu_seconds"], memory_kib=memory,
                             io=fields((p / "io").read_text()), cgroup=cg))
        except OSError:
            continue
    return dict(time_ns=time.monotonic_ns(), host_memory_kib=fields(Path("/proc/meminfo").read_text()),
                host_cpu=Path("/proc/stat").read_text().splitlines()[0],
                host_vmstat=fields(Path("/proc/vmstat").read_text()),
                processes=rows, cgroups=groups,
                totals_kib={scope: {key: sum(r["memory_kib"].get(key, 0) for r in rows if r["scope"] == scope)
                                   for key in ("Pss", "Pss_Anon", "Pss_File", "Pss_Shmem", "Rss", "Swap")}
                            for scope in ("sandbox", "platform")})


def advise_cold(paths):
    """File-scoped DONTNEED only. Not device-cache or application-cache eviction."""
    result = dict(files=0, logical_bytes=0, errors=[])
    for path in paths:
        for directory, dirs, names in os.walk(path, followlinks=False):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(directory, d))]
            for name in names:
                p = Path(directory) / name
                try:
                    s = p.lstat()
                    if not stat.S_ISREG(s.st_mode):
                        continue
                    with p.open("rb", buffering=0) as f:
                        os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
                    result["files"] += 1
                    result["logical_bytes"] += s.st_size
                except OSError as e:
                    result["errors"].append(str(e))
    return result
