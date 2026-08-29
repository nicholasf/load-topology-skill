from topology.discover_tailscale import ManualProvider
from topology.sync import merge
from topology.toml_io import read_toml, write_toml

POND_LOCAL_IP = '192.168.86.118'

FIXTURE_TOPOLOGY = {
    'schema_version': 1,
    'provider': 'manual',
    'last_refreshed': '2026-06-11T10-00-00',
    'machines': [
        {
            'name': 'pond', 'hostname': 'pond', 'local_ip': POND_LOCAL_IP, 'os': 'linux',
            'role': 'LLM Node', 'ssh': True, 'gpu': 'RTX 4090', 'vram': '24GB',
            'last_verified': '2026-06-11',
        },
    ],
}


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


# -- merge with ip_key='local_ip' --

def _discovered(hostname, ip, os_name='linux'):
    return {'hostname': hostname, 'tailscale_ip': ip, 'os': os_name, 'online': True, 'is_self': False}


def test_merge_manual_ip_key_updated():
    existing = [{'name': 'pond', 'hostname': 'pond', 'local_ip': '192.168.86.100'}]
    merged, changes = merge(existing, [_discovered('pond', POND_LOCAL_IP)], ip_key='local_ip')
    assert merged[0]['local_ip'] == POND_LOCAL_IP
    assert any('local_ip' in c for c in changes)


def test_merge_manual_preserves_manual_keys():
    existing = [{'name': 'pond', 'hostname': 'pond', 'local_ip': POND_LOCAL_IP, 'role': 'LLM Node', 'gpu': 'RTX 4090'}]
    merged, changes = merge(existing, [_discovered('pond', POND_LOCAL_IP)], ip_key='local_ip')
    assert merged[0]['role'] == 'LLM Node'
    assert merged[0]['gpu'] == 'RTX 4090'
    assert changes == []


def test_merge_manual_offline_uses_correct_key():
    existing = [{'name': 'pond', 'hostname': 'pond', 'local_ip': POND_LOCAL_IP}]
    merged, changes = merge(existing, [], ip_key='local_ip')
    assert merged[0]['local_ip'] == '(offline)'
    assert any('offline' in c for c in changes)


# -- integration: sync against a temp TOPOLOGIES_HOME --

def test_sync_manual_topology_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('TOPOLOGIES_HOME', str(tmp_path))

    topology_path = tmp_path / 'topology.toml'
    write_toml(FIXTURE_TOPOLOGY, str(topology_path))

    from topology.sync import get_topology_path, main

    assert get_topology_path() == str(topology_path)

    main()

    result = read_toml(str(topology_path))
    assert result['machines'][0]['local_ip'] == POND_LOCAL_IP
    assert '**Last refreshed:**' not in str(result)
    assert 'last_refreshed' in result
    assert (tmp_path / 'topology-backup.toml').exists()
