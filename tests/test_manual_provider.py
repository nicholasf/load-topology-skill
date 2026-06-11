import os
import shutil

import pytest

from discover_tailscale import ManualProvider
from sync import build_table, merge, parse_table, read_provider, update_last_refreshed


POND_LOCAL_IP = '192.168.86.118'

FIXTURE_TOPOLOGY = f"""\
**Schema version:** 1
**Provider:** manual
**Last refreshed:** 2026-06-11T10-00-00

| name | hostname | local-ip | os | role | ssh | gpu | vram | last-verified |
|------|----------|----------|----|------|-----|-----|------|---------------|
| pond | pond | {POND_LOCAL_IP} | linux | LLM Node | yes | RTX 4090 | 24GB | 2026-06-11 |
"""


# -- ManualProvider --

def test_manual_provider_returns_correct_shape():
    provider = ManualProvider([{'hostname': 'pond', 'ip': POND_LOCAL_IP, 'os': 'linux'}])
    result = provider.discover()
    assert len(result) == 1
    m = result[0]
    assert m['hostname'] == 'pond'
    assert m['tailscale_ip'] == POND_LOCAL_IP
    assert m['os'] == 'linux'
    assert m['online'] is True
    assert m['is_self'] is False


def test_manual_provider_empty_list():
    assert ManualProvider([]).discover() == []


def test_manual_provider_os_defaults_to_empty_string():
    result = ManualProvider([{'hostname': 'h', 'ip': '10.0.0.1'}]).discover()
    assert result[0]['os'] == ''


def test_manual_provider_multiple_machines():
    machines = [
        {'hostname': 'pond', 'ip': '192.168.86.118', 'os': 'linux'},
        {'hostname': 'gollum', 'ip': '192.168.86.50', 'os': 'linux'},
    ]
    result = ManualProvider(machines).discover()
    assert len(result) == 2
    assert result[1]['hostname'] == 'gollum'
    assert result[1]['tailscale_ip'] == '192.168.86.50'


# -- read_provider --

def test_read_provider_detects_manual():
    lines = ['**Schema version:** 1', '**Provider:** manual', '']
    assert read_provider(lines) == 'manual'


def test_read_provider_detects_tailscale():
    lines = ['**Provider:** tailscale']
    assert read_provider(lines) == 'tailscale'


def test_read_provider_defaults_to_tailscale_when_absent():
    lines = ['# Topology', '']
    assert read_provider(lines) == 'tailscale'


def test_read_provider_is_case_insensitive():
    lines = ['**Provider:** Manual']
    assert read_provider(lines) == 'manual'


# -- merge with ip_column='local-ip' --

def _manual_row(**overrides):
    cols = ['name', 'hostname', 'local-ip', 'os', 'role', 'ssh', 'gpu', 'vram', 'last-verified']
    row = {col: '—' for col in cols}
    row.update(overrides)
    return row


def _discovered(hostname, ip, os_name='linux'):
    return {'hostname': hostname, 'tailscale_ip': ip, 'os': os_name, 'online': True, 'is_self': False}


def test_merge_manual_ip_column_updated():
    existing = [_manual_row(hostname='pond', **{'local-ip': '192.168.86.100'})]
    merged, changes = merge(existing, [_discovered('pond', POND_LOCAL_IP)], ip_column='local-ip')
    assert merged[0]['local-ip'] == POND_LOCAL_IP
    assert any('local-ip' in c for c in changes)


def test_merge_manual_preserves_manual_columns():
    existing = [_manual_row(hostname='pond', **{'local-ip': POND_LOCAL_IP, 'role': 'LLM Node', 'gpu': 'RTX 4090'})]
    merged, changes = merge(existing, [_discovered('pond', POND_LOCAL_IP)], ip_column='local-ip')
    assert merged[0]['role'] == 'LLM Node'
    assert merged[0]['gpu'] == 'RTX 4090'
    assert changes == []


def test_merge_manual_offline_uses_correct_column():
    existing = [_manual_row(hostname='pond', **{'local-ip': POND_LOCAL_IP})]
    merged, changes = merge(existing, [], ip_column='local-ip')
    assert merged[0]['local-ip'] == '(offline)'
    assert any('offline' in c for c in changes)


# -- integration: sync against a temp SKILLS_HOME --

def test_sync_manual_topology_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('SKILLS_HOME', str(tmp_path))

    topology_path = tmp_path / 'topology.md'
    topology_path.write_text(FIXTURE_TOPOLOGY)

    # Import sync functions after monkeypatching env
    from sync import backup, get_topology_path, main

    # Confirm path resolution picks up our temp dir
    assert get_topology_path() == str(topology_path)

    # Run sync main() — should use ManualProvider, not Tailscale
    main()

    result = topology_path.read_text()
    assert POND_LOCAL_IP in result
    assert '**Last refreshed:**' in result
    # Backup created
    assert (tmp_path / 'topology-backup.md').exists()
