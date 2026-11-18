import math
"""Build timelines from actual monotonic events, never summed medians."""
import json
from pathlib import Path
import re
import statistics
import sys


def analyze(directory):
    row = json.loads((directory/'result.json').read_text())
    events, rpc = [], []
    for line in (directory/'host.log').read_text().splitlines():
        if 'VM_FORK stage ' in line:
            d = dict(re.findall(r'(\w+)=([^\s]+)', line.split('VM_FORK stage ',1)[1]))
            if 'mono_ns' not in d:
                continue
            d['mono_ns'] = int(d['mono_ns'])
            if row['start_ns'] <= d['mono_ns'] <= row['api_ns']:
                events.append(d)
        elif 'E2B_TIMING ' in line:
            try:
                d = json.loads(line.split('E2B_TIMING ',1)[1])
                if row['start_ns'] <= d['started_ns'] <= row['exec_done_ns']:
                    rpc.append(d)
            except ValueError:
                pass
    beginnings = [e for e in events if e['phase'] == 'pause_begin']
    assert len(beginnings) == 1, (directory, beginnings)
    start = beginnings[0]
    events = [e for e in events if e['op'] == start['op']]
    parent_pid = start['pid']
    children = {e['pid'] for e in events if e['pid'] != parent_pid}
    assert len(children) == 1
    child_pid = children.pop()
    def point(phase, pid=parent_pid):
        found = [e['mono_ns'] for e in events if e['phase'] == phase and e['pid'] == pid]
        assert len(found) == 1, (phase, pid, found)
        return found[0]
    parent_resume = point('resume_done')
    child_resume = point('resume_done', child_pid)
    row['parent_pause_ms'] = (parent_resume-point('pause_begin'))/1e6
    row['parent_all_vcpus_stopped_ms'] = (parent_resume-point('vcpus_paused'))/1e6
    row['vcpu_quiesce_ms'] = (point('vcpus_paused')-point('pause_begin'))/1e6
    row['child_resume_ms'] = (child_resume-row['start_ns'])/1e6
    row['parent_resume_ms'] = (parent_resume-row['start_ns'])/1e6
    row['operation'] = start['op']
    spans = []
    def span(lane, label, a, b):
        assert b >= a, (label, a, b)
        spans.append({'lane': lane, 'label': label, 'start_ms': (a-row['start_ns'])/1e6,
                      'end_ms': (b-row['start_ns'])/1e6, 'duration_ms': (b-a)/1e6})
    span('客户端', 'HTTP fork', row['start_ns'], row['api_ns'])
    span('客户端', 'SDK connect', row['api_ns'], row['connect_ns'])
    span('客户端', 'exec → Ready', row['exec_ns'], row['ready_ns'])
    span('客户端', '解释器启动 → print', row['ready_ns'], row['print_ns'])
    span('父 VM 暂停窗口', '暂停请求 → 恢复完成', point('pause_begin'), parent_resume)
    for label, a, b in [
        ('暂停/状态捕获', 'pause_begin', 'snapshot_done'),
        ('线程退出/对象释放', 'snapshot_done', 'host_fork_begin'),
        ('宿主 fork', 'host_fork_begin', 'host_fork_done'),
        ('复用 KVM / 恢复设备', 'runtime_start', 'runtime_ready'),
        ('屏障/等待/恢复运行', 'runtime_ready', 'resume_done')]:
        span('父 VM', label, point(a), point(b))
    for label, a, b in [
        ('子进程 / KVM 初始化', 'host_fork_done', 'kvm_created'),
        ('内存注册/vCPU/设备恢复', 'kvm_created', 'device_state_restored'),
        ('线程就绪', 'device_state_restored', 'runtime_ready'),
        ('屏障/等待/恢复运行', 'runtime_ready', 'resume_done')]:
        span('子 VM', label, point(a, child_pid), point(b, child_pid))
    for label, pid in [('父 API', parent_pid), ('子 API', child_pid)]:
        span(label, 'API 启动至绑定', point('runtime_start', pid), point('api_bound', pid))
    admins = [e for e in rpc if e.get('action') == 'sandbox-fork' and e.get('sid') == row['child_id']]
    assert len(admins) == 1
    admin = admins[0]
    span('控制面', '请求分发/暂停前准备', admin['started_ns'], point('pause_begin'))
    span('控制面', '恢复后控制处理*', max(parent_resume,child_resume), admin['ended_ns'])
    for e in rpc:
        if e['stage'] == 'namespace' and e.get('sid') == row['child_id']:
            span('控制面', '网络命名空间', e['started_ns'], e['ended_ns'])
        if e['stage'] == 'durable_save':
            span('服务端持久化', '状态提交', e['started_ns'], e['ended_ns'])
        if e.get('action') == 'sandbox-network-complete' and e.get('sid') == row['child_id']:
            span('异步网络', '网络完成 RPC', e['started_ns'], e['ended_ns'])
    row['spans'] = spans
    row['phase_events'] = events
    row['trace_notes'] = ['CLOCK_MONOTONIC timestamps on the same host; namespaces do not change the host clock.',
        'Restore control aggregate includes connection/identity and host processing; no unmeasured subinterval is invented.',
        'Persistence spans are service events inside this serial request, including asynchronous network state commits.',
        'Guest progress is a 10 ms observation, not an exact pause clock.']
    return row


def main():
    root = Path(sys.argv[1])
    rows = [analyze(p.parent) for p in sorted(root.glob('*/*/result.json')) if p.parent.name != 'warmup']
    assert len(rows) == 150 and all(r['success'] and not r['owned_remaining'] for r in rows)
    result = {}
    for language in ['python','node','ruby']:
        group = [r for r in rows if r['language'] == language]
        assert len(group) == 50
        metrics = {}
        for key in ['parent_pause_ms','parent_all_vcpus_stopped_ms','vcpu_quiesce_ms',
                    'child_resume_ms','ready_ms','print_ms','preparation_ms','parent_progress_gap_ms']:
            values = sorted(r[key] for r in group)
            metrics[key] = {'n': 50, 'median': statistics.median(values),
                            'p95': values[math.ceil(.95*len(values))-1], 'p99': values[math.ceil(.99*len(values))-1], 'max': values[-1]}
        median = metrics['print_ms']['median']
        representative = min(group,key=lambda r:abs(r['print_ms']-median))
        maximum = max(group,key=lambda r:r['print_ms'])
        result[language] = {'metrics': metrics, 'representative': representative,
                            'maximum': maximum}
    (root/'analyzed.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v['metrics'] for k,v in result.items()},indent=2))


if __name__ == '__main__':
    main()
