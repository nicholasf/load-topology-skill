import json
from unittest.mock import MagicMock, patch

import pytest

from discover import (
    MODEL_STATE_HEADER,
    AGENT_STATE_HEADER,
    build_agent_state,
    build_model_state,
    find_section,
    probe_llama_context_window,
    probe_ollama_context_window,
    read_existing_agent_reasoning_buffers,
)


# ── probe_llama_context_window ────────────────────────────────────────────────

def test_probe_llama_context_window_returns_n_ctx():
    with patch('discover.http_json', return_value={'n_ctx': 65536}):
        assert probe_llama_context_window('pond') == '65536'


def test_probe_llama_context_window_missing_key_returns_dash():
    with patch('discover.http_json', return_value={'other_key': 'value'}):
        assert probe_llama_context_window('pond') == '—'


def test_probe_llama_context_window_server_down_returns_dash():
    with patch('discover.http_json', return_value=None):
        assert probe_llama_context_window('pond') == '—'


# ── probe_ollama_context_window ───────────────────────────────────────────────

def _mock_urlopen(response_data: dict):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(response_data).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


def test_probe_ollama_context_window_returns_context_length():
    mock_resp = _mock_urlopen({'model_info': {'llama.context_length': 131072}})
    with patch('urllib.request.urlopen', return_value=mock_resp):
        assert probe_ollama_context_window('gollum', 'qwen3-coder:30b') == '131072'


def test_probe_ollama_context_window_matches_any_architecture_prefix():
    mock_resp = _mock_urlopen({'model_info': {'qwen2.context_length': 32768}})
    with patch('urllib.request.urlopen', return_value=mock_resp):
        assert probe_ollama_context_window('gollum', 'qwen2.5-coder:14b') == '32768'


def test_probe_ollama_context_window_missing_model_info_returns_dash():
    mock_resp = _mock_urlopen({})
    with patch('urllib.request.urlopen', return_value=mock_resp):
        assert probe_ollama_context_window('gollum', 'qwen3-coder:30b') == '—'


def test_probe_ollama_context_window_missing_context_length_key_returns_dash():
    mock_resp = _mock_urlopen({'modelinfo': {'other': 'data'}})
    with patch('urllib.request.urlopen', return_value=mock_resp):
        assert probe_ollama_context_window('gollum', 'qwen3-coder:30b') == '—'


def test_probe_ollama_context_window_exception_returns_dash():
    with patch('urllib.request.urlopen', side_effect=Exception('connection refused')):
        assert probe_ollama_context_window('gollum', 'qwen3-coder:30b') == '—'


# ── build_model_state ─────────────────────────────────────────────────────────

SAMPLE_DISCOVERIES = {
    'pond': {
        'models': {
            'llama_server': {'up': True, 'models': ['qwen3-coder-30b.gguf'], 'context_window': '65536'},
            'ollama': {'up': False, 'models': [], 'context_window': '—'},
        },
        'ggufs': None,
    }
}


def test_build_model_state_header_is_model_state():
    lines = build_model_state(SAMPLE_DISCOVERIES)
    assert lines[0] == MODEL_STATE_HEADER


def test_build_model_state_includes_context_window_column():
    lines = build_model_state(SAMPLE_DISCOVERIES)
    header_line = next(l for l in lines if l.startswith('| hostname'))
    assert 'context_window' in header_line


def test_build_model_state_context_window_value_in_row():
    lines = build_model_state(SAMPLE_DISCOVERIES)
    llama_row = next(l for l in lines if 'llama-server' in l and 'pond' in l)
    assert '65536' in llama_row


def test_build_model_state_down_backend_shows_dash_for_context():
    lines = build_model_state(SAMPLE_DISCOVERIES)
    ollama_row = next(l for l in lines if 'ollama' in l and 'pond' in l)
    assert 'down' in ollama_row


def test_build_model_state_empty_discoveries():
    lines = build_model_state({})
    assert lines[0] == MODEL_STATE_HEADER
    assert any('| hostname' in l for l in lines)


# ── build_agent_state ─────────────────────────────────────────────────────────

SAMPLE_AGENT_ROWS = [
    {
        'hostname': 'pond',
        'agent': 'hermes',
        'endpoint': 'http://pond:8642',
        'status': 'up',
        'process': 'running',
        'last-seen': '2026-06-08T09-00-00',
    }
]


def test_build_agent_state_includes_reasoning_buffer_column():
    lines = build_agent_state(SAMPLE_AGENT_ROWS)
    header_line = next(l for l in lines if l.startswith('| hostname'))
    assert 'reasoning_buffer' in header_line


def test_build_agent_state_defaults_reasoning_buffer_to_dash():
    lines = build_agent_state(SAMPLE_AGENT_ROWS, preserved_buffers={})
    data_row = next(l for l in lines if 'hermes' in l and 'pond' in l)
    assert data_row.endswith('| — |')


def test_build_agent_state_preserves_existing_reasoning_buffer():
    preserved = {('pond', 'hermes'): '12000'}
    lines = build_agent_state(SAMPLE_AGENT_ROWS, preserved_buffers=preserved)
    data_row = next(l for l in lines if 'hermes' in l and 'pond' in l)
    assert '12000' in data_row


def test_build_agent_state_no_rows_returns_empty_notice():
    lines = build_agent_state([])
    assert any('No agents' in l for l in lines)


def test_build_agent_state_header_is_agent_state():
    lines = build_agent_state(SAMPLE_AGENT_ROWS)
    assert lines[0] == AGENT_STATE_HEADER


# ── read_existing_agent_reasoning_buffers ─────────────────────────────────────

TOPOLOGY_WITH_BUFFERS = """## Agent State
*Last updated: 2026-06-08T09-00-00*

| hostname | agent | endpoint | status | process | last-seen | reasoning_buffer |
|---|---|---|---|---|---|---|
| pond | hermes | http://pond:8642 | up | running | 2026-06-08 | 12000 |
| pond | goose | ws://pond:3284 | down | not found | — | — |
""".splitlines()

TOPOLOGY_NO_AGENT_STATE = """# Topology

| name | hostname |
|---|---|
| — | pond |
""".splitlines()


def test_read_existing_buffers_finds_values():
    result = read_existing_agent_reasoning_buffers(TOPOLOGY_WITH_BUFFERS)
    assert result[('pond', 'hermes')] == '12000'


def test_read_existing_buffers_dash_for_unset():
    result = read_existing_agent_reasoning_buffers(TOPOLOGY_WITH_BUFFERS)
    assert result[('pond', 'goose')] == '—'


def test_read_existing_buffers_empty_when_no_section():
    result = read_existing_agent_reasoning_buffers(TOPOLOGY_NO_AGENT_STATE)
    assert result == {}


def test_read_existing_buffers_empty_when_no_reasoning_buffer_column():
    lines = """## Agent State
*Last updated: 2026-06-08T09-00-00*

| hostname | agent | endpoint | status | process | last-seen |
|---|---|---|---|---|---|
| pond | hermes | http://pond:8642 | up | running | 2026-06-08 |
""".splitlines()
    result = read_existing_agent_reasoning_buffers(lines)
    # reasoning_buffer column absent — default '—'
    assert result[('pond', 'hermes')] == '—'
