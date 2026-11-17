#!/usr/bin/env python3
"""Reproduce the isolated DNS, certificate, and mlink configuration repairs.

Default: inspect and print a plan. Apply only during an agreed idle window:
  sudo python3 repair_deployment.py --apply
Existing instances block endpoint restarts. Other session services are not stopped.
Requires write_sandbox_configs.py in the same directory and the existing deployment.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import write_sandbox_configs as cfg

# Section 1: DNS-only namespace egress. This script is embedded, not downloaded.
DNS_SCRIPT = r"""#!/bin/bash
set -euo pipefail
# DNS-only egress for the isolated comparison namespace; host resolver unchanged.
ip link show bdns-host >/dev/null 2>&1 || ip link add bdns-host type veth peer name bdns-guest
ip link show bdns-guest >/dev/null 2>&1 && ip link set bdns-guest netns bench113
ip addr replace 169.254.253.1/30 dev bdns-host
ip link set bdns-host up
nsenter --net=/run/netns/bench113 ip addr replace 169.254.253.2/30 dev bdns-guest
nsenter --net=/run/netns/bench113 ip link set bdns-guest up
nsenter --net=/run/netns/bench113 ip route replace 7.184.23.114/32 via 169.254.253.1 dev bdns-guest
nsenter --net=/run/netns/bench113 ip route replace default via 169.254.253.1 dev bdns-guest metric 500
for proto in udp tcp; do
 nsenter --net=/run/netns/bench113 iptables -t nat -C POSTROUTING -o bdns-guest -d 7.184.23.114 -p "$proto" --dport 53 -j MASQUERADE 2>/dev/null || nsenter --net=/run/netns/bench113 iptables -t nat -A POSTROUTING -o bdns-guest -d 7.184.23.114 -p "$proto" --dport 53 -j MASQUERADE
 iptables -C FORWARD -i bdns-host -d 7.184.23.114 -p "$proto" --dport 53 -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -i bdns-host -d 7.184.23.114 -p "$proto" --dport 53 -j ACCEPT
 iptables -C FORWARD -o bdns-host -s 7.184.23.114 -p "$proto" --sport 53 -m conntrack --ctstate ESTABLISHED -j ACCEPT 2>/dev/null || iptables -I FORWARD 1 -o bdns-host -s 7.184.23.114 -p "$proto" --sport 53 -m conntrack --ctstate ESTABLISHED -j ACCEPT
 iptables -t nat -C POSTROUTING -s 169.254.253.2 -d 7.184.23.114 -p "$proto" --dport 53 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 169.254.253.2 -d 7.184.23.114 -p "$proto" --dport 53 -j MASQUERADE
done

# Cube eBPF forwarding bypasses guest-side netfilter; translate its DNS at host ingress.
nsenter --net=/run/netns/bench113 ip route replace 119.29.29.29/32 via 169.254.253.1 dev bdns-guest
for proto in udp tcp; do
 iptables -t nat -C PREROUTING -i bdns-host -d 119.29.29.29 -p "$proto" --dport 53 -j DNAT --to-destination 7.184.23.114 2>/dev/null || iptables -t nat -A PREROUTING -i bdns-host -d 119.29.29.29 -p "$proto" --dport 53 -j DNAT --to-destination 7.184.23.114
 iptables -t nat -C POSTROUTING -s 192.0.2.113 -d 7.184.23.114 -p "$proto" --dport 53 -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 192.0.2.113 -d 7.184.23.114 -p "$proto" --dport 53 -j MASQUERADE
done
ip route replace 192.0.2.113/32 via 169.254.253.2 dev bdns-host
"""

def repair_dns(apply):
    target = cfg.DEPLOY / 'bench113-dns-egress.sh'
    cfg.write(target, DNS_SCRIPT, apply, 0o755)
    unit = '''[Unit]
Description=DNS-only egress for isolated CubeSandbox comparison network
Requires=bench113-layout.service
After=bench113-layout.service network-online.target
Before=cube-sandbox-cubelet.service
[Service]
Type=oneshot
ExecStart=/bin/bash /home/hong/deploy/comparison/bench113-dns-egress.sh
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
'''
    cfg.write('/etc/systemd/system/bench113-dns-egress.service', unit, apply, 0o644)
    cfg.write('/etc/systemd/system/cube-sandbox-cubelet.service.d/dns-egress.conf',
              '[Unit]\nRequires=bench113-dns-egress.service\nAfter=bench113-dns-egress.service\n', apply, 0o644)
    cfg.configure_cube(apply)
    if apply:
        cfg.run(['bash', target])
        cfg.run(['systemctl', 'daemon-reload'])
        cfg.run(['systemctl', 'enable', '--now', 'bench113-dns-egress.service'])
        cfg.run(['systemctl', 'restart', 'cube-sandbox-cubelet.service'])
        # This host-resolver integration is deliberately disabled by a condition.
        # Do not enable it or create its opt-in file.
        cfg.run(['systemctl', 'reset-failed', 'cube-sandbox-dns.service'])

# Section 2: Renew short-lived test certificates without changing private keys.
def needs_renewal(path):
    return subprocess.run(['openssl', 'x509', '-checkend', str(7 * 86400),
                           '-noout', '-in', str(path)], capture_output=True).returncode != 0

def renew(product, apply):
    c = cfg.access(product)
    root = Path(c['work_dir'])
    leaf_changed = False
    for name in ('demo-ca.crt', 'tls.crt'):
        path = root / name
        if not needs_renewal(path):
            print('CERTIFICATE VALID', product, name)
            continue
        print('RENEW CERTIFICATE', product, name)
        leaf_changed |= name == 'tls.crt'
        if not apply:
            continue
        if name == 'demo-ca.crt':
            pem = cfg.run(['openssl', 'x509', '-in', path, '-signkey', root / 'demo-ca.key', '-days', '365'])
        else:
            pem = cfg.run(['openssl', 'x509', '-req', '-in', root / 'tls.csr', '-CA', root / 'demo-ca.crt',
                           '-CAkey', root / 'demo-ca.key', '-set_serial', str(time.time_ns()), '-days', '365',
                           '-extfile', root / 'tls.ext', '-extensions', 'server_cert'])
        cfg.write(path, pem, True)
    return leaf_changed

# Section 3: Reload only idle Kuasar API/proxy endpoints when a leaf changed.
def restart_endpoints(product):
    root = Path(cfg.access(product)['work_dir'])
    for role in ('conductor', 'proxy'):
        config = str(root / (role + '.yaml'))
        found = []
        for proc in Path('/proc').glob('[0-9]*'):
            try:
                args = [x.decode() for x in (proc / 'cmdline').read_bytes().split(b'\0') if x]
                if len(args) >= 5 and args[1:3] == [role, 'serve'] and config in args:
                    found.append((proc, args))
            except (OSError, UnicodeError):
                pass
        if len(found) != 1:
            raise RuntimeError(f'Cannot identify exactly one {product} {role}; refusing broad restart')
        proc, command = found[0]
        # Retain the existing process environment without printing credentials.
        environment = dict(item.decode().split('=', 1) for item in (proc / 'environ').read_bytes().split(b'\0') if b'=' in item)
        unit = f'bench-{product}-{role}-renewed'
        cgroup = (proc / 'cgroup').read_text()
        if unit + '.service' in cgroup:
            cfg.run(['systemctl', 'restart', unit])
            continue
        envfile = root / (role + '-repair.env')
        cfg.write(envfile, ''.join(k + '=' + json.dumps(v) + '\n' for k, v in environment.items()), True)
        envfile.chmod(0o600)
        os.kill(int(proc.name), signal.SIGTERM)
        for _ in range(100):
            if not proc.exists():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError('Endpoint did not exit; no SIGKILL was sent')
        cfg.run(['systemd-run', '--unit=' + unit, '--property=Restart=on-failure',
                 '--property=NetworkNamespacePath=/run/netns/' + cfg.NAMESPACES[product],
                 '--property=EnvironmentFile=' + str(envfile), '--property=LimitNOFILE=1048576', *command])

# Section 4: Restore mlink settings without rebuilding any binary.
def repair_mlink(apply):
    cfg.configure_mlink(apply)
    if apply:
        cfg.run(['systemctl', 'restart', 'bench-private-mlink.service'])
        for _ in range(300):
            try:
                data = json.loads(cfg.run(['nsenter', '--net=/run/netns/bench113-m', 'curl',
                                          '-fsS', '--max-time', '2', 'http://127.0.0.1:28082/internal/status']))
                if data['capacity']['ready'] == 64 and data['capacity']['assigned'] == 0:
                    return
            except (subprocess.CalledProcessError, ValueError):
                pass
            time.sleep(1)
        raise RuntimeError('mlink did not return to 64 ready slots within 300 seconds')

# Section 5: Preflight guards and ordered application; no benchmark is started.
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo.')
    held_lock = cfg.lock()
    if args.apply:
        # Check all impacted products before the first mutation.
        for product in ('cube', 'kuasar-off', 'kuasar-uffd', 'kuasar-mlink'):
            cfg.require_idle(product)
    repair_dns(args.apply)
    for product in ('kuasar-off', 'kuasar-uffd'):
        if renew(product, args.apply) and args.apply:
            restart_endpoints(product)
    repair_mlink(args.apply)
    print('Repair sequence finished. Run lifecycle smoke checks before a formal benchmark.')

if __name__ == '__main__':
    main()
