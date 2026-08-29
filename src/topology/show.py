#!/usr/bin/env python3
"""show.py — pretty-print topology.toml and all sidecar files as aligned tables.

topology.toml (and every topology-*.toml sidecar) is the source of truth; this
module is a read-only display layer over it — it writes nothing.
"""

import os
import sys

from .sync import get_topology_path, list_sidecars
from .toml_io import read_toml


def _format_cell(value) -> str:
    if isinstance(value, list):
        return ', '.join(str(v) for v in value)
    return str(value)


def render_table(rows: list[dict]) -> list[str]:
    cols = list(dict.fromkeys(k for row in rows for k in row))
    cells = [[_format_cell(row.get(c, '—')) for c in cols] for row in rows]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(cols)]

    def render_row(values: list[str]) -> str:
        return '| ' + ' | '.join(v.ljust(w) for v, w in zip(values, widths)) + ' |'

    lines = [render_row(cols), '|' + '|'.join('-' * (w + 2) for w in widths) + '|']
    lines += [render_row(row) for row in cells]
    return lines


def render_toml(path: str) -> str:
    data = read_toml(path)
    lines = [f'## {os.path.basename(path)}', '']

    for key, value in data.items():
        if not isinstance(value, list):
            lines.append(f'{key}: {value}')
    if any(not isinstance(v, list) for v in data.values()):
        lines.append('')

    for key, value in data.items():
        if not isinstance(value, list) or not value:
            continue
        lines.append(f'[{key}]')
        lines.extend(render_table(value))
        lines.append('')

    return '\n'.join(lines).rstrip()


def main() -> None:
    topology_path = get_topology_path()

    if not os.path.exists(topology_path):
        print(f'Topology not found: {topology_path}', file=sys.stderr)
        sys.exit(1)

    sidecars = list_sidecars(os.path.dirname(topology_path))
    files = [topology_path] + sidecars

    for i, path in enumerate(files):
        if i > 0:
            print()
            print('─' * 60)
            print()
        print(render_toml(path))

    print()
    if sidecars:
        print(f'({len(sidecars)} sidecar file(s): {", ".join(os.path.basename(s) for s in sidecars)})')
    else:
        print('(no sidecar files found)')


if __name__ == '__main__':
    main()
