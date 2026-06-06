#!/usr/bin/env python3
"""Benchmark an LLM node and record stats in topology.md."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

BENCHMARK_PROMPT = "Explain the concept of recursion in programming in two sentences."
BENCH_COLUMNS = ['hostname', 'model', 'timestamp', 'ttft_ms', 'tok_s', 'runs']


def get_topology_path() -> str:
    skills_home = os.environ.get('SKILLS_HOME', os.path.expanduser('~/.agents/skills'))
    default = os.path.join(skills_home, 'topology.md')
    return os.environ.get('TOPOLOGY_PATH', default)


def run_single(hostname: str, port: int, model: str) -> tuple[float, float, float]:
    """Stream one completion request; return (ttft_ms, tok_s, total_ms)."""
    url = f"http://{hostname}:{port}/v1/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": BENCHMARK_PROMPT}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": 200,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    t0 = time.perf_counter()
    ttft_ms = None
    completion_tokens = 0

    with urllib.request.urlopen(req, timeout=60) as resp:
        while True:
            raw = resp.readline()
            if not raw:
                break
            line = raw.decode().strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue

            if ttft_ms is None:
                choices = obj.get("choices", [])
                if choices and choices[0].get("delta", {}).get("content"):
                    ttft_ms = (time.perf_counter() - t0) * 1000

            if obj.get("usage"):
                completion_tokens = obj["usage"].get("completion_tokens", 0)

    total_ms = (time.perf_counter() - t0) * 1000
    gen_ms = total_ms - (ttft_ms or 0)
    tok_s = round(completion_tokens / (gen_ms / 1000), 1) if completion_tokens and gen_ms > 0 else 0.0
    return round(ttft_ms or 0, 1), tok_s, round(total_ms, 1)


def run_benchmark(hostname: str, port: int, model: str, runs: int) -> tuple[float, float]:
    """Run N passes; return (avg_ttft_ms, avg_tok_s)."""
    ttfts, tok_ss = [], []
    for i in range(runs):
        print(f"  run {i + 1}/{runs}...", flush=True)
        ttft, tok_s, total = run_single(hostname, port, model)
        ttfts.append(ttft)
        tok_ss.append(tok_s)
        print(f"    ttft={ttft:.0f}ms  tok/s={tok_s:.1f}  total={total:.0f}ms")
    return round(sum(ttfts) / len(ttfts), 1), round(sum(tok_ss) / len(tok_ss), 1)


def parse_benchmark_table(lines: list[str]) -> tuple[int, int, list[dict]]:
    """Return (section_start, table_end, rows) for the LLM Benchmarks table."""
    section_start = -1
    for i, line in enumerate(lines):
        if line.strip() == '## LLM Benchmarks':
            section_start = i
            break
    if section_start == -1:
        return -1, -1, []

    table_header = -1
    for i in range(section_start + 1, len(lines)):
        if lines[i].strip().startswith('| hostname |'):
            table_header = i
            break
    if table_header == -1:
        return section_start, section_start + 1, []

    table_end = len(lines)
    for i in range(table_header + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or (stripped.startswith('-') and not stripped.startswith('|-')):
            table_end = i
            break

    rows = []
    for line in lines[table_header + 2:table_end]:
        if not line.strip() or not line.startswith('|'):
            continue
        parts = [p.strip() for p in line.split('|')[1:-1]]
        if len(parts) >= len(BENCH_COLUMNS):
            rows.append(dict(zip(BENCH_COLUMNS, parts)))
    return section_start, table_end, rows


def build_benchmark_table(rows: list[dict]) -> list[str]:
    header = '| ' + ' | '.join(BENCH_COLUMNS) + ' |'
    sep = '|' + '|'.join('---' for _ in BENCH_COLUMNS) + '|'
    lines = [header, sep]
    for row in rows:
        lines.append('| ' + ' | '.join(str(row.get(col, '—')) for col in BENCH_COLUMNS) + ' |')
    return lines


def record_result(
    topology_path: str, hostname: str, model: str,
    ttft_ms: float, tok_s: float, runs: int,
) -> None:
    with open(topology_path) as f:
        lines = f.read().splitlines()

    timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    new_row: dict[str, str] = {
        'hostname': hostname,
        'model': model,
        'timestamp': timestamp,
        'ttft_ms': str(ttft_ms),
        'tok_s': str(tok_s),
        'runs': str(runs),
    }

    section_start, table_end, rows = parse_benchmark_table(lines)
    rows = [r for r in rows if not (r['hostname'] == hostname and r['model'] == model)]
    rows.append(new_row)
    rows.sort(key=lambda r: (r['hostname'], r['model']))
    new_table = build_benchmark_table(rows)

    if section_start == -1:
        lines += ['', '## LLM Benchmarks', ''] + new_table + ['']
    else:
        table_header = -1
        for i in range(section_start + 1, len(lines)):
            if lines[i].strip().startswith('| hostname |'):
                table_header = i
                break
        if table_header == -1:
            lines = lines[:section_start + 1] + [''] + new_table + lines[section_start + 1:]
        else:
            lines = lines[:table_header] + new_table + lines[table_end:]

    with open(topology_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"Recorded in {topology_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark an LLM node via OpenAI-compat API")
    parser.add_argument('hostname', help="target machine hostname or IP")
    parser.add_argument('model', help="model name as reported by the server")
    parser.add_argument('--port', type=int, default=9337)
    parser.add_argument('--runs', type=int, default=3)
    args = parser.parse_args()

    print(f"Benchmarking {args.model} on {args.hostname}:{args.port} ({args.runs} runs)")
    print(f"Prompt: {BENCHMARK_PROMPT!r}\n")

    try:
        avg_ttft, avg_tok_s = run_benchmark(args.hostname, args.port, args.model, args.runs)
    except urllib.error.URLError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nAverage:  ttft={avg_ttft}ms  tok/s={avg_tok_s}")

    topology_path = get_topology_path()
    if os.path.exists(topology_path):
        record_result(topology_path, args.hostname, args.model, avg_ttft, avg_tok_s, args.runs)
    else:
        print(f"Warning: topology not found at {topology_path}, results not saved")


if __name__ == '__main__':
    main()
