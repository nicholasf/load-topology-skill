#!/usr/bin/env python3
import json
import subprocess
import sys
from abc import ABC, abstractmethod


class NetworkProvider(ABC):
    @abstractmethod
    def discover(self) -> list[dict]:
        """Return list of machine dicts: hostname, tailscale_ip, os, online, is_self."""
        pass


class TailscaleProvider(NetworkProvider):
    def discover(self) -> list[dict]:
        try:
            result = subprocess.run(
                ['tailscale', 'status', '--json'],
                capture_output=True,
                text=True,
                check=True
            )
        except FileNotFoundError:
            raise RuntimeError('Tailscale is not installed or not in PATH')
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Tailscale status command failed: {e.stderr}')

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f'Failed to parse Tailscale JSON output: {e}')

        machines = []

        if 'Self' in data:
            machines.append(self._parse_entry(data['Self'], is_self=True))

        for peer in data.get('Peer', {}).values():
            machines.append(self._parse_entry(peer, is_self=False))

        return machines

    def _parse_entry(self, entry: dict, is_self: bool) -> dict:
        hostname = entry.get('HostName', '')

        tailscale_ip = ''
        for ip in entry.get('TailscaleIPs', []):
            if ':' not in ip:
                tailscale_ip = ip
                break

        online = True if is_self else entry.get('Online', False)

        return {
            'hostname': hostname,
            'tailscale_ip': tailscale_ip,
            'os': entry.get('OS', ''),
            'online': online,
            'is_self': is_self,
        }


def main():
    try:
        machines = TailscaleProvider().discover()
    except RuntimeError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    for m in machines:
        status = 'online' if m['online'] else 'offline'
        self_marker = ' (this machine)' if m['is_self'] else ''
        print(f"{m['hostname']} ({m['tailscale_ip']}) — {m['os']} — {status}{self_marker}")


if __name__ == '__main__':
    main()
