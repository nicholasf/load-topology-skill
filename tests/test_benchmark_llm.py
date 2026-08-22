import os
import tempfile

import pytest

from topology.benchmark_llm import (
    BENCH_COLUMNS,
    build_benchmark_table,
    parse_benchmark_table,
    record_result,
)


def make_bench_row(**overrides):
    row = {col: '—' for col in BENCH_COLUMNS}
    row.update(overrides)
    return row


def make_bench_lines(rows=None):
    header = '| ' + ' | '.join(BENCH_COLUMNS) + ' |'
    sep = '|' + '|'.join('---' for _ in BENCH_COLUMNS) + '|'
    lines = [header, sep]
    for row in (rows or []):
        lines.append('| ' + ' | '.join(str(row.get(col, '—')) for col in BENCH_COLUMNS) + ' |')
    return lines


def make_topology_file(content):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
    f.write(content)
    f.close()
    return f.name


# -- parse_benchmark_table --

def test_parse_finds_section_and_rows():
    row = make_bench_row(hostname='gollum', model='qwen3', ttft_ms='300.0', tok_s='45.2', runs='3')
    lines = ['# Topology', '', '## LLM Benchmarks', ''] + make_bench_lines([row])
    section_start, table_end, rows = parse_benchmark_table(lines)
    assert section_start == 2
    assert len(rows) == 1
    assert rows[0]['hostname'] == 'gollum'
    assert rows[0]['tok_s'] == '45.2'


def test_parse_no_section_returns_sentinel():
    lines = ['# Topology', '', 'No benchmarks here.']
    assert parse_benchmark_table(lines) == (-1, -1, [])


def test_parse_section_without_table_returns_empty_rows():
    lines = ['# Topology', '', '## LLM Benchmarks', '']
    section_start, table_end, rows = parse_benchmark_table(lines)
    assert section_start == 2
    assert rows == []


def test_parse_separator_row_not_in_rows():
    row = make_bench_row(hostname='gollum', model='qwen3')
    lines = ['## LLM Benchmarks', ''] + make_bench_lines([row])
    _, _, rows = parse_benchmark_table(lines)
    assert len(rows) == 1
    assert all('---' not in v for v in rows[0].values())


# -- build_benchmark_table --

def test_build_header_starts_with_hostname():
    lines = build_benchmark_table([])
    assert lines[0].startswith('| hostname |')


def test_build_has_separator():
    lines = build_benchmark_table([])
    assert '---' in lines[1]


def test_build_one_line_per_row_in_column_order():
    rows = [
        make_bench_row(hostname='a', model='m1', tok_s='40.0'),
        make_bench_row(hostname='b', model='m2', tok_s='50.0'),
    ]
    lines = build_benchmark_table(rows)
    assert len(lines) == 4  # header + sep + 2 rows
    assert 'a' in lines[2] and 'm1' in lines[2]
    assert 'b' in lines[3] and 'm2' in lines[3]


# -- record_result --

def test_record_creates_section_when_absent():
    path = make_topology_file('# Topology\n\n| name | hostname |\n|---|---|\n| — | gollum |\n')
    try:
        record_result(path, 'gollum', 'qwen3', 300.0, 45.2, 3)
        content = open(path).read()
        assert '## LLM Benchmarks' in content
        assert 'gollum' in content
        assert '45.2' in content
    finally:
        os.unlink(path)


def test_record_appends_new_row_without_touching_existing():
    existing = '| gollum | other-model | 2026-01-01T00-00-00 | 200.0 | 60.0 | 3 |'
    path = make_topology_file(
        '# Topology\n\n## LLM Benchmarks\n\n'
        '| hostname | model | timestamp | ttft_ms | tok_s | runs |\n'
        '|---|---|---|---|---|---|\n'
        f'{existing}\n'
    )
    try:
        record_result(path, 'gollum', 'new-model', 310.0, 42.1, 3)
        content = open(path).read()
        assert 'other-model' in content
        assert 'new-model' in content
    finally:
        os.unlink(path)


def test_record_replaces_existing_row_for_same_hostname_and_model():
    old = '| gollum | qwen3 | 2026-01-01T00-00-00 | 200.0 | 60.0 | 3 |'
    path = make_topology_file(
        '# Topology\n\n## LLM Benchmarks\n\n'
        '| hostname | model | timestamp | ttft_ms | tok_s | runs |\n'
        '|---|---|---|---|---|---|\n'
        f'{old}\n'
    )
    try:
        record_result(path, 'gollum', 'qwen3', 320.0, 48.5, 5)
        bench_rows = [
            l for l in open(path).read().splitlines()
            if l.startswith('| gollum | qwen3 |')
        ]
        assert len(bench_rows) == 1
        assert '48.5' in bench_rows[0]
        assert '60.0' not in bench_rows[0]
    finally:
        os.unlink(path)


def test_record_rows_sorted_by_hostname_then_model():
    path = make_topology_file('# Topology\n')
    try:
        record_result(path, 'zzz-host', 'model-a', 100.0, 50.0, 1)
        record_result(path, 'aaa-host', 'model-b', 200.0, 40.0, 1)
        lines = [l for l in open(path).read().splitlines() if l.startswith('| ') and 'hostname' not in l and '---' not in l]
        hostnames = [l.split('|')[1].strip() for l in lines]
        assert hostnames == sorted(hostnames)
    finally:
        os.unlink(path)
