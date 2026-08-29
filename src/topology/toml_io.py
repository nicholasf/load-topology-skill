#!/usr/bin/env python3
"""
toml_io.py — shared TOML read/write for topology.toml and its sidecar files.

Replaces the hand-rolled markdown-table parsers previously duplicated across
sync.py, discover.py, and init.py. Reading uses stdlib tomllib; writing is a
small hand-rolled serializer (tomllib is read-only) sized for this project's
flat schema: top-level scalars plus arrays-of-tables of flat dicts — the same
shape playbooks already round-trip by hand, so no new dependency is needed.
"""

import tomllib


def read_toml(path: str) -> dict:
    with open(path, 'rb') as f:
        return tomllib.load(f)


def _format_value(value) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return '[' + ', '.join(_format_value(v) for v in value) + ']'
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def write_toml(data: dict, path: str) -> None:
    """Write top-level scalars, then each list-of-dicts as [[key]] array-of-tables."""
    lines = []

    for key, value in data.items():
        if isinstance(value, list):
            continue
        lines.append(f'{key} = {_format_value(value)}')

    for key, value in data.items():
        if not isinstance(value, list):
            continue
        for entry in value:
            lines.append('')
            lines.append(f'[[{key}]]')
            for k, v in entry.items():
                lines.append(f'{k} = {_format_value(v)}')

    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
