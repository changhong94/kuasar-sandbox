"""Read-only, configured process accounting; no hard-coded host service names."""
from pathlib import Path
import re


def resources(config):
    patterns = config.get('resource_cgroup_patterns', [])
    excluded = config.get('resource_cgroup_exclude', [])
    if not patterns:
        return {'supported': False, 'reason': 'resource cgroup ownership not configured'}
    table, owned = {}, set()
    for path in Path('/proc').glob('[0-9]*'):
        try:
            pid = int(path.name)
            group = (path / 'cgroup').read_text()
            parent = int((path / 'stat').read_text().rsplit(')', 1)[1].split()[1])
            table[pid] = (parent, path)
            if any(p in group for p in patterns) and not any(p in group for p in excluded):
                owned.add(pid)
        except (OSError, ValueError):
            continue
    while True:
        children = {pid for pid, (parent, _) in table.items() if parent in owned} - owned
        if not children:
            break
        owned.update(children)
    detail = {}
    for pid in owned:
        try:
            path = table[pid][1]
            pss = int(re.search(r'^Pss:\s+(\d+)', (path / 'smaps_rollup').read_text(), re.M)[1])
            detail[str(pid)] = [(path / 'comm').read_text().strip(), pss, len(list((path / 'fd').iterdir()))]
        except (OSError, KeyError, TypeError):
            continue
    return {'supported': True, 'pss_mib': sum(v[1] for v in detail.values()) / 1024,
            'fds': sum(v[2] for v in detail.values()), 'processes': detail}
