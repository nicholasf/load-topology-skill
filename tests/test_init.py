import os
from unittest.mock import patch

import pytest

from topology.init import (
    MANUAL_COLUMNS,
    TAILSCALE_COLUMNS,
    build_table,
    get_topology_path,
    machines_to_rows,
    parse_machines_arg,
    write_topology,
)


# -- get_topology_path --

def test_get_topology_path_uses_skills_home(monkeypatch, tmp_path):
    monkeypatch.setenv('SKILLS_HOME', str(tmp_path))
    assert get_topology_path() == str(tmp_path / 'topology.md')


def test_get_topology_path_defaults_when_unset(monkeypatch):
    monkeypatch.delenv('SKILLS_HOME', raising=False)
    assert get_topology_path().endswith('topology.md')


# -- build_table --

def test_build_table_empty_tailscale():
    lines = build_table(TAILSCALE_COLUMNS)
    assert len(lines) == 2
    assert lines[0].startswith('| name |')
    assert 'tailscale-ip' in lines[0]
    assert '---' in lines[1]


def test_build_table_empty_manual():
    lines = build_table(MANUAL_COLUMNS)
    assert 'local-ip' in lines[0]
    assert 'tailscale-ip' not in lines[0]


def test_build_table_with_rows():
    rows = [{'name': 'pond', 'hostname': 'pond', 'local-ip': '192.168.86.118'}]
    lines = build_table(MANUAL_COLUMNS, rows)
    assert len(lines) == 3
    assert 'pond' in lines[2]
    assert '192.168.86.118' in lines[2]


# -- machines_to_rows --

def test_machines_to_rows_sets_name_and_hostname():
    machines = [{'hostname': 'pond', 'ip': '192.168.86.118'}]
    rows = machines_to_rows(machines, MANUAL_COLUMNS)
    assert rows[0]['name'] == 'pond'
    assert rows[0]['hostname'] == 'pond'
    assert rows[0]['local-ip'] == '192.168.86.118'


def test_machines_to_rows_fills_remaining_columns_with_dash():
    machines = [{'hostname': 'pond', 'ip': '192.168.86.118'}]
    rows = machines_to_rows(machines, MANUAL_COLUMNS)
    assert rows[0]['os'] == '—'
    assert rows[0]['gpu'] == '—'


def test_machines_to_rows_multiple():
    machines = [
        {'hostname': 'pond', 'ip': '192.168.86.118'},
        {'hostname': 'gollum', 'ip': '192.168.86.50'},
    ]
    rows = machines_to_rows(machines, MANUAL_COLUMNS)
    assert len(rows) == 2
    assert rows[1]['hostname'] == 'gollum'


# -- parse_machines_arg --

def test_parse_machines_arg_single():
    result = parse_machines_arg('pond 192.168.86.118')
    assert result == [{'hostname': 'pond', 'ip': '192.168.86.118'}]


def test_parse_machines_arg_multiple():
    result = parse_machines_arg('pond 192.168.86.118,gollum 192.168.86.50')
    assert len(result) == 2
    assert result[1] == {'hostname': 'gollum', 'ip': '192.168.86.50'}


def test_parse_machines_arg_invalid_raises():
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        parse_machines_arg('just-hostname')


# -- write_topology --

def test_write_topology_creates_file(tmp_path):
    path = str(tmp_path / 'topology.md')
    table = build_table(MANUAL_COLUMNS)
    write_topology('manual', table, path)
    assert os.path.exists(path)
    content = open(path).read()
    assert '**Provider:** manual' in content
    assert '**Schema version:** 1' in content
    assert '**Last refreshed:**' in content
    assert '| name |' in content


def test_write_topology_tailscale_includes_tailscale_ip(tmp_path):
    path = str(tmp_path / 'topology.md')
    table = build_table(TAILSCALE_COLUMNS)
    write_topology('tailscale', table, path)
    content = open(path).read()
    assert '**Provider:** tailscale' in content
    assert 'tailscale-ip' in content


def test_write_topology_creates_parent_dirs(tmp_path):
    path = str(tmp_path / 'nested' / 'dir' / 'topology.md')
    write_topology('manual', build_table(MANUAL_COLUMNS), path)
    assert os.path.exists(path)


# -- main() integration --

def test_main_tailscale_non_interactive(tmp_path, monkeypatch):
    monkeypatch.setenv('SKILLS_HOME', str(tmp_path))
    with patch('topology.init.run_sync', return_value=True):
        from topology.init import main
        import sys
        with patch.object(sys, 'argv', ['init.py', '--provider', 'tailscale']):
            main()
    content = (tmp_path / 'topology.md').read_text()
    assert '**Provider:** tailscale' in content
    assert 'tailscale-ip' in content


def test_main_manual_non_interactive(tmp_path, monkeypatch):
    monkeypatch.setenv('SKILLS_HOME', str(tmp_path))
    with patch('topology.init.run_sync', return_value=True):
        from topology.init import main
        import sys
        with patch.object(sys, 'argv', ['init.py', '--provider', 'manual', '--machines', 'pond 192.168.86.118']):
            main()
    content = (tmp_path / 'topology.md').read_text()
    assert '**Provider:** manual' in content
    assert '192.168.86.118' in content
    assert 'pond' in content


def test_main_exits_if_topology_exists_without_force(tmp_path, monkeypatch):
    monkeypatch.setenv('SKILLS_HOME', str(tmp_path))
    (tmp_path / 'topology.md').write_text('existing')
    import sys
    with patch.object(sys, 'argv', ['init.py', '--provider', 'tailscale']):
        with pytest.raises(SystemExit) as exc:
            from topology.init import main
            main()
    assert exc.value.code == 0
    assert (tmp_path / 'topology.md').read_text() == 'existing'


def test_main_force_overwrites_existing(tmp_path, monkeypatch):
    monkeypatch.setenv('SKILLS_HOME', str(tmp_path))
    (tmp_path / 'topology.md').write_text('old content')
    with patch('topology.init.run_sync', return_value=True):
        import sys
        with patch.object(sys, 'argv', ['init.py', '--provider', 'manual', '--machines', 'pond 192.168.86.118', '--force']):
            from topology.init import main
            main()
    assert 'old content' not in (tmp_path / 'topology.md').read_text()
