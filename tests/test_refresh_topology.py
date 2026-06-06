import os
from unittest.mock import patch

import pytest

from refresh_topology import (
    COLUMNS,
    build_table,
    get_topology_path,
    merge,
    parse_table,
    update_last_refreshed,
)


def make_table_lines(rows=None):
    header = '| ' + ' | '.join(COLUMNS) + ' |'
    separator = '|' + '|'.join('---' for _ in COLUMNS) + '|'
    lines = [header, separator]
    for row in (rows or []):
        lines.append('| ' + ' | '.join(row.get(col, '—') for col in COLUMNS) + ' |')
    return lines


def sample_row(**overrides):
    row = {col: '—' for col in COLUMNS}
    row.update(overrides)
    return row


def discovered(hostname, tailscale_ip='100.1.2.3', os_name='Linux', online=True, is_self=False):
    return {'hostname': hostname, 'tailscale_ip': tailscale_ip, 'os': os_name, 'online': online, 'is_self': is_self}


# -- get_topology_path --

def test_get_topology_path_uses_topology_path_env(monkeypatch):
    monkeypatch.setenv('TOPOLOGY_PATH', '/custom/topology.md')
    assert get_topology_path() == '/custom/topology.md'


def test_get_topology_path_falls_back_to_skills_home(monkeypatch):
    monkeypatch.delenv('TOPOLOGY_PATH', raising=False)
    monkeypatch.setenv('SKILLS_HOME', '/my/skills')
    assert get_topology_path() == '/my/skills/topology.md'


def test_get_topology_path_defaults_when_both_unset(monkeypatch):
    monkeypatch.delenv('TOPOLOGY_PATH', raising=False)
    monkeypatch.delenv('SKILLS_HOME', raising=False)
    assert get_topology_path() == os.path.expanduser('~/.agents/skills/topology.md')


# -- parse_table --

def test_parse_table_valid_11_column_table():
    row = sample_row(hostname='myhost', **{'tailscale-ip': '100.1.2.3', 'os': 'Linux'})
    lines = ['# Topology', ''] + make_table_lines([row]) + ['', 'Narrative.']
    table_start, table_end, rows = parse_table(lines)
    assert table_start == 2
    assert len(rows) == 1
    assert rows[0]['hostname'] == 'myhost'
    assert rows[0]['tailscale-ip'] == '100.1.2.3'
    assert rows[0]['os'] == 'Linux'


def test_parse_table_no_table_returns_negative_sentinel():
    lines = ['# Topology', '', 'No table here.']
    assert parse_table(lines) == (-1, -1, [])


def test_parse_table_at_end_of_file_no_trailing_blank():
    row = sample_row(hostname='myhost')
    lines = ['# Topology', ''] + make_table_lines([row])
    table_start, table_end, rows = parse_table(lines)
    assert table_end == len(lines)
    assert len(rows) == 1


def test_parse_table_separator_row_not_in_rows():
    row = sample_row(hostname='myhost')
    lines = make_table_lines([row])
    _, _, rows = parse_table(lines)
    assert len(rows) == 1
    assert all(not v.startswith('---') for v in rows[0].values())


# -- merge --

def test_merge_new_machine_added_with_dashes_in_manual_columns():
    merged, changes = merge([], [discovered('newhost')])
    assert len(merged) == 1
    assert merged[0]['hostname'] == 'newhost'
    assert merged[0]['tailscale-ip'] == '100.1.2.3'
    assert merged[0]['name'] == '—'
    assert merged[0]['role'] == '—'
    assert any('new machine' in c for c in changes)


def test_merge_changed_ip_updates_ip_preserves_manual_columns():
    existing = [sample_row(hostname='myhost', **{'tailscale-ip': '100.1.2.3', 'role': 'server', 'ssh': 'yes'})]
    merged, changes = merge(existing, [discovered('myhost', tailscale_ip='100.9.9.9')])
    assert merged[0]['tailscale-ip'] == '100.9.9.9'
    assert merged[0]['role'] == 'server'
    assert merged[0]['ssh'] == 'yes'
    assert any('100.1.2.3' in c and '100.9.9.9' in c for c in changes)


def test_merge_absent_machine_marked_offline():
    existing = [sample_row(hostname='oldhost', **{'tailscale-ip': '100.1.2.3'})]
    merged, changes = merge(existing, [])
    assert merged[0]['tailscale-ip'] == '(offline)'
    assert any('offline' in c for c in changes)


def test_merge_no_changes_returns_empty_changes_list():
    existing = [sample_row(hostname='myhost', **{'tailscale-ip': '100.1.2.3', 'os': 'Linux'})]
    merged, changes = merge(existing, [discovered('myhost', tailscale_ip='100.1.2.3')])
    assert changes == []
    assert merged[0]['tailscale-ip'] == '100.1.2.3'


# -- build_table --

def test_build_table_header_starts_with_name():
    lines = build_table([])
    assert lines[0].startswith('| name |')


def test_build_table_has_separator_row():
    lines = build_table([])
    assert '---' in lines[1]


def test_build_table_one_line_per_row_in_column_order():
    rows = [
        sample_row(name='host-a', hostname='host-a', **{'tailscale-ip': '100.1.2.3'}),
        sample_row(name='host-b', hostname='host-b', **{'tailscale-ip': '100.1.2.4'}),
    ]
    lines = build_table(rows)
    assert len(lines) == 4  # header + separator + 2 rows
    assert 'host-a' in lines[2]
    assert 'host-b' in lines[3]


# -- update_last_refreshed --

def test_update_last_refreshed_updates_existing_line():
    lines = [
        '# Topology',
        '**Last refreshed:** 2026-01-01T00-00-00',
        '',
        '| name | hostname |',
    ]
    result = update_last_refreshed(lines, table_start=3)
    assert '**Last refreshed:**' in result[1]
    assert '2026-01-01T00-00-00' not in result[1]
    assert len(result) == len(lines)


def test_update_last_refreshed_inserts_before_table_when_absent():
    lines = [
        '# Topology',
        '',
        '| name | hostname |',
    ]
    result = update_last_refreshed(lines, table_start=2)
    assert '**Last refreshed:**' in result[2]
    assert len(result) == len(lines) + 1
