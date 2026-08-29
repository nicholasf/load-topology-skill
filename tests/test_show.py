from unittest.mock import patch

from topology.show import main, render_table, render_toml
from topology.toml_io import write_toml


def test_render_table_aligns_columns_and_uses_union_of_keys():
    rows = [{'name': 'pond', 'gpu': 'RTX 4090'}, {'name': 'hut'}]
    lines = render_table(rows)
    assert lines[0].startswith('| name')
    assert 'gpu' in lines[0]
    assert '—' in lines[3]  # hut's missing gpu


def test_render_table_formats_list_values_as_comma_joined():
    rows = [{'hostname': 'pond', 'models': ['a', 'b']}]
    lines = render_table(rows)
    assert 'a, b' in lines[2]


def test_render_toml_shows_scalars_and_sections(tmp_path):
    path = str(tmp_path / 'topology.toml')
    write_toml({
        'schema_version': 1,
        'provider': 'tailscale',
        'machines': [{'name': 'pond', 'hostname': 'pond'}],
    }, path)
    out = render_toml(path)
    assert 'topology.toml' in out
    assert 'schema_version: 1' in out
    assert 'provider: tailscale' in out
    assert '[machines]' in out
    assert 'pond' in out


def test_render_toml_omits_empty_arrays(tmp_path):
    path = str(tmp_path / 'topology.toml')
    write_toml({'schema_version': 1, 'machines': []}, path)
    out = render_toml(path)
    assert '[machines]' not in out


def test_main_prints_topology_and_sidecars(tmp_path, monkeypatch, capsys):
    write_toml({'machines': [{'name': 'pond'}]}, str(tmp_path / 'topology.toml'))
    write_toml({'endpoint': 'http://pond:8642'}, str(tmp_path / 'topology-ask-agent.toml'))
    monkeypatch.setenv('TOPOLOGIES_HOME', str(tmp_path))

    main()
    out = capsys.readouterr().out
    assert 'topology.toml' in out
    assert 'topology-ask-agent.toml' in out
    assert '(1 sidecar file(s):' in out


def test_main_no_sidecars_prints_notice(tmp_path, monkeypatch, capsys):
    write_toml({'machines': [{'name': 'pond'}]}, str(tmp_path / 'topology.toml'))
    monkeypatch.setenv('TOPOLOGIES_HOME', str(tmp_path))

    main()
    out = capsys.readouterr().out
    assert '(no sidecar files found)' in out


def test_main_missing_topology_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv('TOPOLOGIES_HOME', str(tmp_path))
    with patch('sys.exit', side_effect=SystemExit) as exit_mock:
        try:
            main()
        except SystemExit:
            pass
        exit_mock.assert_called_once_with(1)
