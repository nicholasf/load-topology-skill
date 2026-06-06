import json
import subprocess
from unittest.mock import patch

import pytest

from discover_tailscale import NetworkProvider, TailscaleProvider


def test_network_provider_is_abstract():
    with pytest.raises(TypeError):
        NetworkProvider()


def test_discover_returns_self_and_peers():
    data = {
        'Self': {'HostName': 'self-machine', 'TailscaleIPs': ['100.1.2.3'], 'OS': 'Linux'},
        'Peer': {
            'p1': {'HostName': 'peer-one', 'TailscaleIPs': ['100.1.2.4'], 'OS': 'Windows', 'Online': True},
            'p2': {'HostName': 'peer-two', 'TailscaleIPs': ['100.1.2.5'], 'OS': 'macOS', 'Online': False},
        },
    }
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps(data), stderr='')
        result = TailscaleProvider().discover()

    assert len(result) == 3
    self_entry = result[0]
    assert self_entry['hostname'] == 'self-machine'
    assert self_entry['tailscale_ip'] == '100.1.2.3'
    assert self_entry['os'] == 'Linux'
    assert self_entry['online'] is True
    assert self_entry['is_self'] is True

    assert result[1]['hostname'] == 'peer-one'
    assert result[1]['online'] is True
    assert result[1]['is_self'] is False

    assert result[2]['hostname'] == 'peer-two'
    assert result[2]['online'] is False
    assert result[2]['is_self'] is False


def test_discover_self_is_always_online():
    data = {
        'Self': {'HostName': 'self-machine', 'TailscaleIPs': ['100.1.2.3'], 'OS': 'Linux', 'Online': False},
        'Peer': {},
    }
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps(data), stderr='')
        result = TailscaleProvider().discover()

    assert result[0]['online'] is True
    assert result[0]['is_self'] is True


def test_discover_skips_ipv6_uses_first_ipv4():
    data = {
        'Self': {'HostName': 'h', 'TailscaleIPs': ['fd7a::1', 'fe80::1', '100.1.2.3'], 'OS': 'Linux'},
        'Peer': {},
    }
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps(data), stderr='')
        result = TailscaleProvider().discover()

    assert result[0]['tailscale_ip'] == '100.1.2.3'


def test_discover_empty_peers_returns_only_self():
    data = {
        'Self': {'HostName': 'solo', 'TailscaleIPs': ['100.1.2.3'], 'OS': 'Linux'},
        'Peer': {},
    }
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps(data), stderr='')
        result = TailscaleProvider().discover()

    assert len(result) == 1
    assert result[0]['hostname'] == 'solo'


def test_discover_binary_not_found_raises_runtime_error():
    with patch('subprocess.run', side_effect=FileNotFoundError()):
        with pytest.raises(RuntimeError, match='not installed'):
            TailscaleProvider().discover()


def test_discover_nonzero_exit_raises_runtime_error():
    with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'tailscale', stderr='auth error')):
        with pytest.raises(RuntimeError):
            TailscaleProvider().discover()


def test_discover_invalid_json_raises_runtime_error():
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout='not json', stderr='')
        with pytest.raises(RuntimeError, match='Failed to parse'):
            TailscaleProvider().discover()
