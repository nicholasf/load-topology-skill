#!/usr/bin/env python3
"""show.py — print a combined view of topology.md and all sidecar files."""

import os
import sys

from .sync import get_topology_path, list_sidecars


def main() -> None:
    topology_path = get_topology_path()
    skills_home = os.environ.get('SKILLS_HOME', os.path.expanduser('~/.agents/skills'))

    if not os.path.exists(topology_path):
        print(f'Topology not found: {topology_path}', file=sys.stderr)
        sys.exit(1)

    sidecars = list_sidecars(skills_home)
    files = [topology_path] + sidecars

    for i, path in enumerate(files):
        if i > 0:
            print()
            print('─' * 60)
            print()
        print(f'## {os.path.basename(path)}')
        print()
        with open(path) as f:
            print(f.read().rstrip())

    print()
    if sidecars:
        print(f'({len(sidecars)} sidecar file(s): {", ".join(os.path.basename(s) for s in sidecars)})')
    else:
        print('(no sidecar files found)')


if __name__ == '__main__':
    main()
