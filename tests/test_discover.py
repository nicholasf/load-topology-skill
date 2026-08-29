import json
from unittest.mock import MagicMock, patch

from topology.discover import (
    build_agent_state,
    build_model_state,
    probe_llama_context_window,
    probe_ollama_context_window,
    read_existing_agent_reasoning_buffers,
)


# ── probe_llama_context_window ────────────────────────────────────────────────

def test_probe_llama_context_window_returns_n_ctx():
    with patch('topology.discover.http_json', return_value={'n_ctx': 65536}):
        assert probe_llama_context_window('pond') == 65536


def test_probe_llama_context_window_missing_key_returns_none():
    with patch('topology.discover.http_json', return_value={'other_key': 'value'}):
        assert probe_llama_context_window('pond') is None


def test_probe_llama_context_window_server_down_returns_none():
    with patch('topology.discover.http_json', return_value=None):
        assert probe_llama_context_window('pond') is None


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
        assert probe_ollama_context_window('gollum', 'qwen3-coder:30b') == 131072


def test_probe_ollama_context_window_matches_any_architecture_prefix():
    mock_resp = _mock_urlopen({'model_info': {'qwen2.context_length': 32768}})
    with patch('urllib.request.urlopen', return_value=mock_resp):
        assert probe_ollama_context_window('gollum', 'qwen2.5-coder:14b') == 32768


def test_probe_ollama_context_window_missing_model_info_returns_none():
    mock_resp = _mock_urlopen({})
    with patch('urllib.request.urlopen', return_value=mock_resp):
        assert probe_ollama_context_window('gollum', 'qwen3-coder:30b') is None


def test_probe_ollama_context_window_missing_context_length_key_returns_none():
    mock_resp = _mock_urlopen({'modelinfo': {'other': 'data'}})
    with patch('urllib.request.urlopen', return_value=mock_resp):
        assert probe_ollama_context_window('gollum', 'qwen3-coder:30b') is None


def test_probe_ollama_context_window_exception_returns_none():
    with patch('urllib.request.urlopen', side_effect=Exception('connection refused')):
        assert probe_ollama_context_window('gollum', 'qwen3-coder:30b') is None


# ── build_model_state ─────────────────────────────────────────────────────────

SAMPLE_DISCOVERIES = {
    'pond': {
        'models': {
            'llama_server': {'up': True, 'models': ['qwen3-coder-30b.gguf'], 'context_window': 65536},
            'ollama': {'up': False, 'models': [], 'context_window': None},
        },
        'ggufs': None,
    }
}


def test_build_model_state_includes_context_window_for_up_backend():
    rows = build_model_state(SAMPLE_DISCOVERIES)
    llama_row = next(r for r in rows if r['backend'] == 'llama-server')
    assert llama_row['context_window'] == 65536
    assert llama_row['status'] == 'up'


def test_build_model_state_down_backend_omits_context_window():
    rows = build_model_state(SAMPLE_DISCOVERIES)
    ollama_row = next(r for r in rows if r['backend'] == 'ollama')
    assert ollama_row['status'] == 'down'
    assert 'context_window' not in ollama_row
    assert 'last_seen' not in ollama_row


def test_build_model_state_empty_discoveries():
    assert build_model_state({}) == []


def test_build_model_state_ggufs_row_only_when_ggufs_not_none():
    discoveries = {'pond': {'models': SAMPLE_DISCOVERIES['pond']['models'], 'ggufs': ['a.gguf', 'b.gguf']}}
    rows = build_model_state(discoveries)
    gguf_row = next(r for r in rows if r['backend'] == 'ggufs')
    assert gguf_row['models'] == ['a.gguf', 'b.gguf']
    assert gguf_row['status'] == 'installed'


# ── build_agent_state ─────────────────────────────────────────────────────────

SAMPLE_AGENT_ROWS = [
    {
        'hostname': 'pond',
        'agent': 'hermes',
        'endpoint': 'http://pond:8642',
        'status': 'up',
        'process': 'running',
        'last_seen': '2026-06-08T09-00-00',
    }
]


def test_build_agent_state_no_preserved_buffer_omits_key():
    rows = build_agent_state(SAMPLE_AGENT_ROWS, preserved_buffers={})
    assert 'reasoning_buffer' not in rows[0]


def test_build_agent_state_preserves_existing_reasoning_buffer():
    preserved = {('pond', 'hermes'): 12000}
    rows = build_agent_state(SAMPLE_AGENT_ROWS, preserved_buffers=preserved)
    assert rows[0]['reasoning_buffer'] == 12000


def test_build_agent_state_no_rows_returns_empty_list():
    assert build_agent_state([]) == []


# ── read_existing_agent_reasoning_buffers ─────────────────────────────────────

def test_read_existing_buffers_finds_values():
    agent_state = [
        {'hostname': 'pond', 'agent': 'hermes', 'reasoning_buffer': 12000},
        {'hostname': 'pond', 'agent': 'goose', 'status': 'down'},
    ]
    result = read_existing_agent_reasoning_buffers(agent_state)
    assert result == {('pond', 'hermes'): 12000}


def test_read_existing_buffers_empty_when_no_agent_state():
    assert read_existing_agent_reasoning_buffers([]) == {}


def test_read_existing_buffers_skips_rows_without_reasoning_buffer():
    agent_state = [{'hostname': 'pond', 'agent': 'hermes', 'status': 'up'}]
    assert read_existing_agent_reasoning_buffers(agent_state) == {}
