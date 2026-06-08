#!/usr/bin/env python3
"""
discover.py — probe all reachable nodes and write live state into topology.md.

Invoked via: /load-topology discover

Probes every machine in the machines table:
  - HTTP:  llama-server (:9337) and Ollama (:11434) for running models
  - SSH:   gpu, vram, local-ip, GGUF inventory
  - HTTP:  configured agent endpoints (hermes_gateway, goose_acp_url columns)
  - SSH:   pgrep scan for known agent processes

Writes/replaces two sections in topology.md:
  ## Model State  — inference backend status, models, and context windows per node
  ## Agent State  — per-node agent liveness and reasoning_buffer
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sync import get_topology_path

AGENT_SSH_USER = os.environ.get('AGENT_SSH_USER', 'nicholasf')

MODEL_STATE_HEADER = '## Model State'
AGENT_STATE_HEADER = '## Agent State'

MODEL_COLS = ['hostname', 'backend', 'port', 'models', 'context_window', 'status', 'last-seen']
AGENT_COLS = ['hostname', 'agent', 'endpoint', 'status', 'process', 'last-seen', 'reasoning_buffer']

KNOWN_AGENT_PROCS = ['hermes', 'goose', 'aider', 'open-webui']


def ts() -> str:
    return datetime.now().strftime('%Y-%m-%dT%H-%M-%S')


# ── SSH ───────────────────────────────────────────────────────────────────────

def ssh_run(host: str, user: str, cmd: str, timeout: int = 10) -> str | None:
    try:
        r = subprocess.run(
            ['ssh',
             '-o', 'ConnectTimeout=5',
             '-o', 'BatchMode=yes',
             '-o', 'StrictHostKeyChecking=no',
             f'{user}@{host}', cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


# ── HTTP ──────────────────────────────────────────────────────────────────────

def http_json(url: str, timeout: int = 3) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def http_up(url: str, timeout: int = 3) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True  # got a response — server is reachable
    except Exception:
        return False


# ── Table parsing (full — preserves all columns) ──────────────────────────────

def parse_full_table(lines: list[str]) -> tuple[int, int, list[str], list[dict]]:
    start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('|') and '| name |' in line:
            start = i
            break
    if start == -1:
        return -1, -1, [], []

    cols = [p.strip() for p in lines[start].split('|')[1:-1]]

    end = len(lines)
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if not s or (s.startswith('-') and not s.startswith('|-')):
            end = i
            break

    rows = []
    for line in lines[start + 2:end]:
        if not line.strip() or not line.startswith('|'):
            continue
        parts = [p.strip() for p in line.split('|')[1:-1]]
        while len(parts) < len(cols):
            parts.append('—')
        rows.append(dict(zip(cols, parts[:len(cols)])))

    return start, end, cols, rows


def build_full_table(cols: list[str], rows: list[dict]) -> list[str]:
    header = '| ' + ' | '.join(cols) + ' |'
    sep = '|' + '|'.join('---' for _ in cols) + '|'
    out = [header, sep]
    for row in rows:
        out.append('| ' + ' | '.join(row.get(c, '—') for c in cols) + ' |')
    return out


# ── Section helpers ───────────────────────────────────────────────────────────

def find_section(lines: list[str], header: str) -> tuple[int, int]:
    start = -1
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            break
    if start == -1:
        return -1, -1
    for i in range(start + 1, len(lines)):
        if lines[i].startswith('## ') and lines[i].strip() != header:
            return start, i
    return start, len(lines)


def replace_or_append(lines: list[str], header: str, content: list[str]) -> list[str]:
    start, end = find_section(lines, header)
    if start == -1:
        return lines + [''] + content
    return lines[:start] + content + lines[end:]


# ── Context window probing ────────────────────────────────────────────────────

def probe_llama_context_window(host: str) -> str:
    """GET /props from llama-server; returns n_ctx as string or '—'."""
    data = http_json(f'http://{host}:9337/props')
    if data and 'n_ctx' in data:
        return str(data['n_ctx'])
    return '—'


def probe_ollama_context_window(host: str, model: str) -> str:
    """POST /api/show to Ollama for a specific model; returns context length or '—'."""
    try:
        body = json.dumps({'name': model}).encode()
        req = urllib.request.Request(
            f'http://{host}:11434/api/show',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        ctx = data.get('modelinfo', {}).get('llama.context_length')
        return str(ctx) if ctx else '—'
    except Exception:
        return '—'


# ── Preserved reasoning_buffer values ────────────────────────────────────────

def read_existing_agent_reasoning_buffers(lines: list[str]) -> dict[tuple[str, str], str]:
    """Read existing reasoning_buffer values from Agent State before overwriting."""
    start, end = find_section(lines, AGENT_STATE_HEADER)
    if start == -1:
        return {}
    result: dict[tuple[str, str], str] = {}
    headers: list[str] | None = None
    for line in lines[start:end]:
        if line.startswith('| hostname'):
            headers = [h.strip() for h in line.split('|')[1:-1]]
        elif headers and line.startswith('|') and '---' not in line:
            values = [v.strip() for v in line.split('|')[1:-1]]
            row = dict(zip(headers, values))
            host = row.get('hostname', '—')
            agent = row.get('agent', '—')
            buf = row.get('reasoning_buffer', '—')
            if host != '—' and agent != '—':
                result[(host, agent)] = buf
    return result


# ── Discovery ─────────────────────────────────────────────────────────────────

def discover_hardware(host: str, user: str, os_name: str) -> dict:
    out: dict[str, str] = {}

    ip = ssh_run(host, user, "ip route get 1 2>/dev/null | awk '{print $7; exit}'")
    if ip:
        out['local-ip'] = ip

    if 'macos' in os_name.lower():
        gpu = ssh_run(host, user,
            "system_profiler SPDisplaysDataType 2>/dev/null"
            " | awk -F': ' '/Chipset Model/{print $2; exit}'")
    else:
        gpu = ssh_run(host, user,
            "lspci 2>/dev/null | grep -i 'vga\\|3d controller\\|display'"
            " | sed 's/.*: //' | head -1")
    if gpu:
        out['gpu'] = gpu[:60]

    vram = ssh_run(host, user,
        "nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1")
    if vram and vram.strip().isdigit():
        out['vram'] = f'{int(vram.strip()) // 1024}GB GDDR6X (CUDA)'
    else:
        vram = ssh_run(host, user,
            "rocm-smi --showmeminfo vram 2>/dev/null"
            " | grep -i 'total memory' | awk '{print $NF}' | head -1")
        if vram and vram.strip().isdigit():
            gb = int(vram.strip()) // (1024 ** 3)
            out['vram'] = f'{gb}GB UMA (ROCm)'

    out['last-verified'] = ts()[:10]
    return out


def list_ggufs(host: str, user: str) -> list[str]:
    out = ssh_run(host, user,
        "ls ~/.local/share/gguf/*.gguf 2>/dev/null | xargs -I{} basename {} 2>/dev/null")
    if not out:
        return []
    return [f.strip() for f in out.splitlines() if f.strip()]


def probe_models(host: str) -> dict:
    ls_data = http_json(f'http://{host}:9337/v1/models')
    ol_data = http_json(f'http://{host}:11434/v1/models')

    ls_up = bool(ls_data and 'data' in ls_data)
    ls_models = [m['id'] for m in ls_data.get('data', [])] if ls_data else []
    ls_ctx = probe_llama_context_window(host) if ls_up else '—'

    ol_up = bool(ol_data and 'data' in ol_data)
    ol_models = [m['id'] for m in ol_data.get('data', [])] if ol_data else []
    ol_ctx = probe_ollama_context_window(host, ol_models[0]) if (ol_up and ol_models) else '—'

    return {
        'llama_server': {
            'up': ls_up,
            'models': ls_models,
            'context_window': ls_ctx,
        },
        'ollama': {
            'up': ol_up,
            'models': ol_models,
            'context_window': ol_ctx,
        },
    }


def probe_agents(host: str, user: str | None, row: dict) -> list[dict]:
    now = ts()
    results = []

    for agent_name, col in [('hermes', 'hermes_gateway'), ('goose', 'goose_acp_url')]:
        endpoint = row.get(col, '—')
        if not endpoint or endpoint == '—':
            continue
        probe_url = endpoint.replace('ws://', 'http://').replace('wss://', 'https://')
        up = http_up(probe_url)
        proc = ssh_run(host, user, f"pgrep -x {agent_name} 2>/dev/null | head -1") if user else None
        results.append({
            'hostname': host,
            'agent': agent_name,
            'endpoint': endpoint,
            'status': 'up' if up else 'down',
            'process': ('running' if proc else 'not found') if user else '(no SSH)',
            'last-seen': now if up else '—',
        })

    if user:
        covered = {r['agent'] for r in results}
        for proc_name in KNOWN_AGENT_PROCS:
            if proc_name in covered:
                continue
            pid = ssh_run(host, user, f"pgrep -x {proc_name} 2>/dev/null | head -1")
            if pid:
                results.append({
                    'hostname': host,
                    'agent': proc_name,
                    'endpoint': '(not configured)',
                    'status': 'process up',
                    'process': 'running',
                    'last-seen': now,
                })

    return results


# ── Section builders ──────────────────────────────────────────────────────────

def build_model_state(discoveries: dict) -> list[str]:
    lines = [MODEL_STATE_HEADER, f'*Last updated: {ts()}*', '']
    h = '| ' + ' | '.join(MODEL_COLS) + ' |'
    sep = '|' + '|'.join('---' for _ in MODEL_COLS) + '|'
    lines += [h, sep]

    for host in sorted(discoveries):
        d = discoveries[host]
        models = d.get('models', {})
        now = ts()

        ls = models.get('llama_server', {})
        model_str = ', '.join(ls.get('models', [])) if ls.get('up') else '—'
        ctx = ls.get('context_window', '—')
        lines.append(
            f'| {host} | llama-server | 9337 | {model_str} | {ctx}'
            f' | {"up" if ls.get("up") else "down"}'
            f' | {now if ls.get("up") else "—"} |'
        )

        ol = models.get('ollama', {})
        model_str = ', '.join(ol.get('models', [])) if ol.get('up') else '—'
        ctx = ol.get('context_window', '—')
        lines.append(
            f'| {host} | ollama | 11434 | {model_str} | {ctx}'
            f' | {"up" if ol.get("up") else "down"}'
            f' | {now if ol.get("up") else "—"} |'
        )

        ggufs = d.get('ggufs')
        if ggufs is not None:
            gguf_str = ', '.join(ggufs) if ggufs else '(none found)'
            lines.append(f'| {host} | ggufs | — | {gguf_str} | — | installed | — |')

    lines.append('')
    return lines


def build_agent_state(all_rows: list[dict], preserved_buffers: dict[tuple[str, str], str] | None = None) -> list[str]:
    if preserved_buffers is None:
        preserved_buffers = {}
    lines = [AGENT_STATE_HEADER, f'*Last updated: {ts()}*', '']
    if not all_rows:
        lines += ['*No agents configured or discovered.*', '']
        return lines
    h = '| ' + ' | '.join(AGENT_COLS) + ' |'
    sep = '|' + '|'.join('---' for _ in AGENT_COLS) + '|'
    lines += [h, sep]
    for row in all_rows:
        host = row.get('hostname', '—')
        agent = row.get('agent', '—')
        buf = preserved_buffers.get((host, agent), '—')
        row_with_buf = dict(row)
        row_with_buf['reasoning_buffer'] = buf
        lines.append('| ' + ' | '.join(str(row_with_buf.get(c, '—')) for c in AGENT_COLS) + ' |')
    lines.append('')
    return lines


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    path = get_topology_path()
    if not os.path.exists(path):
        print(f'Topology not found: {path}', file=sys.stderr)
        sys.exit(1)

    with open(path) as f:
        lines = f.read().splitlines()

    table_start, table_end, cols, rows = parse_full_table(lines)
    if not rows:
        print('No machines table found in topology file.', file=sys.stderr)
        sys.exit(1)

    preserved_buffers = read_existing_agent_reasoning_buffers(lines)

    discoveries: dict[str, dict] = {}
    all_agent_rows: list[dict] = []
    hw_updates: dict[str, dict] = {}

    for row in rows:
        host = row.get('hostname', '').strip()
        if not host or host == '—':
            continue

        can_ssh = row.get('ssh', '').strip().lower() == 'yes'
        user = (row.get('ssh-user', '').strip() or AGENT_SSH_USER) if can_ssh else None
        os_name = row.get('os', 'linux')

        print(f'{host}:', end=' ', flush=True)

        if can_ssh:
            hw = discover_hardware(host, user, os_name)
            hw_updates[host] = hw

        ggufs = list_ggufs(host, user) if can_ssh else None
        models = probe_models(host)
        agents = probe_agents(host, user, row)

        discoveries[host] = {'models': models, 'ggufs': ggufs}
        all_agent_rows.extend(agents)

        parts = []
        if models['llama_server']['up']:
            m = models['llama_server']['models']
            parts.append(f"llama-server:{m[0] if m else 'up'}")
        if models['ollama']['up']:
            parts.append(f"ollama:{len(models['ollama']['models'])} models")
        agent_summary = [f"{a['agent']}:{a['status']}" for a in agents]
        print(
            (', '.join(parts) if parts else 'no inference running') +
            (f'  agents={agent_summary}' if agent_summary else '')
        )

    if hw_updates and cols:
        for row in rows:
            host = row.get('hostname', '')
            if host in hw_updates:
                row.update(hw_updates[host])
        new_table = build_full_table(cols, rows)
        lines = lines[:table_start] + new_table + lines[table_end:]

    lines = replace_or_append(lines, MODEL_STATE_HEADER, build_model_state(discoveries))
    lines = replace_or_append(lines, AGENT_STATE_HEADER, build_agent_state(all_agent_rows, preserved_buffers))

    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f'\nTopology updated: {path}')


if __name__ == '__main__':
    main()
