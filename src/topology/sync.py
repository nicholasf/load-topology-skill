#!/usr/bin/env python3
import fnmatch
import glob
import os
import shutil
import sys
from datetime import datetime  # used by update_last_refreshed

from .discover_tailscale import ManualProvider, TailscaleProvider


COLUMNS = ['name', 'hostname', 'tailscale-ip', 'local-ip', 'os', 'role', 'ssh', 'ssh-user', 'gpu', 'vram', 'last-verified']
MANUAL_COLUMNS = {'name', 'local-ip', 'role', 'ssh', 'ssh-user', 'gpu', 'vram', 'last-verified'}


def get_topology_path() -> str:
    skills_home = os.environ.get('SKILLS_HOME', os.path.expanduser('~/.agents/skills'))
    return os.path.join(skills_home, 'topology.md')


def list_sidecars(skills_home: str) -> list[str]:
    """Return sorted topology-*.md sidecar files, excluding backup files."""
    candidates = glob.glob(os.path.join(skills_home, 'topology-*.md'))
    return sorted(p for p in candidates if not fnmatch.fnmatch(os.path.basename(p), 'topology-backup*.md'))


def backup(topology_path: str) -> None:
    backup_path = os.path.join(os.path.dirname(topology_path), 'topology-backup.md')
    shutil.copy2(topology_path, backup_path)


def parse_table(lines: list[str]) -> tuple[int, int, list[dict]]:
    """Return (table_start, table_end, rows). table_end is the index after the last table line.

    Reads all columns from the actual header row so that extra columns added by
    dependent skills (e.g. hermes_gateway, goose_acp_url) are preserved across syncs.
    """
    table_start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('| name |'):
            table_start = i
            break

    if table_start == -1:
        return -1, -1, []

    # Read actual column names from the header, not the fixed COLUMNS list
    actual_cols = [p.strip() for p in lines[table_start].split('|')[1:-1]]

    # table_end defaults to end of file in case there's no blank line after the table
    table_end = len(lines)
    for i in range(table_start + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or (stripped.startswith('-') and not stripped.startswith('|-')):
            table_end = i
            break

    rows = []
    for line in lines[table_start + 2:table_end]:  # skip header and separator
        if not line.strip() or not line.startswith('|'):
            continue
        parts = [p.strip() for p in line.split('|')[1:-1]]
        while len(parts) < len(actual_cols):
            parts.append('—')
        rows.append(dict(zip(actual_cols, parts[:len(actual_cols)])))

    return table_start, table_end, rows


def read_provider(lines: list[str]) -> str:
    for line in lines:
        if '**Provider:**' in line:
            return line.split('**Provider:**')[1].strip().lower()
    return 'tailscale'


def merge(existing_rows: list[dict], discovered: list[dict], ip_column: str = 'tailscale-ip') -> tuple[list[dict], list[str]]:
    # Derive column set from existing rows so extra columns are preserved for new machines too
    all_cols = list(dict.fromkeys(col for row in existing_rows for col in row)) if existing_rows else COLUMNS

    existing_by_hostname = {r['hostname']: r for r in existing_rows}
    discovered_hostnames = {m['hostname'] for m in discovered}
    changes = []
    merged = []

    for machine in discovered:
        hostname = machine['hostname']
        if hostname in existing_by_hostname:
            row = existing_by_hostname[hostname].copy()
            old_ip = row.get(ip_column, '—')
            row[ip_column] = machine['tailscale_ip']
            row['os'] = machine['os']
            if old_ip != machine['tailscale_ip']:
                changes.append(f"  {hostname}: {ip_column} {old_ip} → {machine['tailscale_ip']}")
        else:
            row = {col: '—' for col in all_cols}
            row['hostname'] = hostname
            row['tailscale-ip'] = machine['tailscale_ip']
            row['os'] = machine['os']
            changes.append(f'  {hostname}: new machine added')
        merged.append(row)

    for row in existing_rows:
        if row['hostname'] not in discovered_hostnames:
            updated = row.copy()
            updated[ip_column] = '(offline)'
            merged.append(updated)
            changes.append(f"  {row['hostname']}: marked offline")

    return merged, changes


def build_table(rows: list[dict]) -> list[str]:
    # Preserve all columns from the rows; keep core COLUMNS order, extras appended
    if rows:
        seen = list(dict.fromkeys(col for row in rows for col in row))
        cols = [c for c in COLUMNS if c in seen] + [c for c in seen if c not in COLUMNS]
    else:
        cols = COLUMNS
    header = '| ' + ' | '.join(cols) + ' |'
    separator = '|' + '|'.join('---' for _ in cols) + '|'
    lines = [header, separator]
    for row in rows:
        lines.append('| ' + ' | '.join(row.get(col, '—') for col in cols) + ' |')
    return lines


def update_last_refreshed(lines: list[str], table_start: int) -> list[str]:
    timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    updated = list(lines)
    for i in range(min(table_start, len(lines))):
        if '**Last refreshed:**' in updated[i]:
            updated[i] = f'**Last refreshed:** {timestamp}'
            return updated
    # Not found — insert before the table
    if table_start >= 0:
        updated.insert(table_start, f'**Last refreshed:** {timestamp}')
    return updated


def main():
    topology_path = get_topology_path()

    if not os.path.exists(topology_path):
        print(f'Topology file not found: {topology_path}', file=sys.stderr)
        sys.exit(1)

    backup(topology_path)

    with open(topology_path) as f:
        lines = f.read().splitlines()

    table_start, table_end, existing_rows = parse_table(lines)

    if table_start == -1:
        print('No machines table found in topology file. Add a table with header row starting "| name |".')
        sys.exit(1)

    provider_name = read_provider(lines)
    if provider_name == 'manual':
        machines = [
            {'hostname': r['hostname'], 'ip': r.get('local-ip', '—'), 'os': r.get('os', '')}
            for r in existing_rows
            if r.get('local-ip', '—') not in ('—', '', '(offline)')
        ]
        provider = ManualProvider(machines)
        ip_column = 'local-ip'
    else:
        provider = TailscaleProvider()
        ip_column = 'tailscale-ip'

    try:
        discovered = provider.discover()
    except RuntimeError as e:
        print(f'Discovery error: {e}', file=sys.stderr)
        sys.exit(1)

    merged_rows, changes = merge(existing_rows, discovered, ip_column)
    new_table_lines = build_table(merged_rows)

    updated_lines = lines[:table_start] + new_table_lines + lines[table_end:]
    updated_lines = update_last_refreshed(updated_lines, table_start)

    with open(topology_path, 'w') as f:
        f.write('\n'.join(updated_lines) + '\n')

    print(f'Topology updated: {topology_path}')
    if changes:
        print('Changes:')
        for change in changes:
            print(change)
    else:
        print('No changes.')
    print()
    print('Tip: run /load-topology discover for deeper per-node data — GPU model, VRAM,')
    print('     local IP, installed GGUFs, running models, and agent process status.')


if __name__ == '__main__':
    main()
