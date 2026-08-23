#!/usr/bin/env python3
"""
playbook.py — resolve a trigger phrase to a named, alias-tagged sequence of
host commands ("playbook") and run it.

Invoked via: /topology run "<phrase>" [--skip-oversight]

Playbooks live in $SKILLS_HOME as topology-playbook*.toml:
  topology-playbook-<node>.toml  — a playbook whose tasks all target one host
  topology-playbooks.toml        — a playbook composed from more than one host

A task's `hosts` is either a `name` from the topology.md machines table
(resolved to `hostname`/`ssh-user` and run over SSH) or the reserved
`localhost`, which runs as a local subprocess with no SSH and no table
lookup. A task may instead be a `ref` to another playbook, which is expanded
in place (composition) — cyclic references are rejected.

No LLM is involved in resolving a phrase or executing a task: alias matching
is exact/normalized string comparison, and every task is reviewed (full
flattened plan printed) before anything runs. A task can require individual
Y/N sign-off ("oversight") — set explicitly by the author or detected by a
keyword heuristic; explicit authoring always wins over the heuristic.
"""

import difflib
import glob
import os
import subprocess
import sys
import tomllib

from .discover import AGENT_SSH_USER, parse_full_table
from .sync import get_topology_path

HEURISTIC_OVERSIGHT_PATTERNS = ['restart', 'kill', 'stop', 'rm ', 'rm\t', 'drop', 'wipe']


class PlaybookError(Exception):
    """A playbook file, reference, or invocation could not be resolved."""


# ── Discovery & parsing ─────────────────────────────────────────────────────

def get_skills_home() -> str:
    return os.path.dirname(get_topology_path())


def list_playbook_files(skills_home: str) -> list[str]:
    """Return sorted topology-playbook*.toml files (node-scoped and shared)."""
    return sorted(glob.glob(os.path.join(skills_home, 'topology-playbook*.toml')))


def parse_playbook_file(path: str) -> list[dict]:
    """Parse one topology-playbook*.toml file into a list of playbook records."""
    try:
        with open(path, 'rb') as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise PlaybookError(f'{path}: invalid TOML — {e}') from e

    playbooks = []
    for entry in data.get('playbook', []):
        if 'name' not in entry:
            raise PlaybookError(f'{path}: a [[playbook]] entry is missing "name"')
        tasks = entry.get('tasks', [])
        for i, task in enumerate(tasks):
            _validate_task(task, entry['name'], i, path)
        playbooks.append({
            'name': entry['name'],
            'aliases': entry.get('aliases', []),
            'description': entry.get('description', ''),
            'tasks': tasks,
            'source': path,
        })
    return playbooks


def _validate_task(task: dict, playbook_name: str, index: int, path: str) -> None:
    where = f'{path}: playbook "{playbook_name}" task {index + 1}'
    is_ref = 'ref' in task
    is_command = 'hosts' in task and 'command' in task
    if is_ref and is_command:
        raise PlaybookError(f'{where}: has both "ref" and "hosts"/"command" — a task is one or the other')
    if not is_ref and not is_command:
        raise PlaybookError(f'{where}: must have "ref", or both "hosts" and "command"')


def normalize_phrase(s: str) -> str:
    return ' '.join(s.strip().lower().split())


def load_playbooks(skills_home: str) -> dict[str, dict]:
    """Glob and parse every playbook file, enforcing global name/alias uniqueness."""
    by_name: dict[str, dict] = {}
    alias_owner: dict[str, str] = {}

    for path in list_playbook_files(skills_home):
        for pb in parse_playbook_file(path):
            if pb['name'] in by_name:
                raise PlaybookError(
                    f'duplicate playbook name "{pb["name"]}" in {path} and {by_name[pb["name"]]["source"]}'
                )
            for alias in pb['aliases']:
                key = normalize_phrase(alias)
                if key in alias_owner:
                    raise PlaybookError(
                        f'alias "{alias}" is used by both "{alias_owner[key]}" and "{pb["name"]}"'
                    )
                alias_owner[key] = pb['name']
            by_name[pb['name']] = pb

    return by_name


# ── Alias resolution ─────────────────────────────────────────────────────────

def resolve_alias(phrase: str, playbooks: dict[str, dict]) -> str | None:
    target = normalize_phrase(phrase)
    for pb in playbooks.values():
        if target in (normalize_phrase(a) for a in pb['aliases']):
            return pb['name']
    return None


def near_miss_candidates(phrase: str, playbooks: dict[str, dict], limit: int = 5) -> list[str]:
    normalized_to_alias = {
        normalize_phrase(alias): alias
        for pb in playbooks.values()
        for alias in pb['aliases']
    }
    matches = difflib.get_close_matches(normalize_phrase(phrase), list(normalized_to_alias), n=limit, cutoff=0.0)
    return [normalized_to_alias[m] for m in matches]


# ── Oversight classification ─────────────────────────────────────────────────

def classify_oversight(task: dict) -> bool:
    """explicit_true > explicit_false > heuristic_match > default_false."""
    if 'oversight' in task:
        return bool(task['oversight'])
    command = task.get('command', '')
    return any(p in command.lower() for p in HEURISTIC_OVERSIGHT_PATTERNS)


# ── Machines table / host resolution ─────────────────────────────────────────

def load_machines_table() -> list[dict]:
    path = get_topology_path()
    if not os.path.exists(path):
        return []
    with open(path) as f:
        lines = f.read().splitlines()
    _, _, _, rows = parse_full_table(lines)
    return rows


def resolve_remote_host(hosts: str, machines: list[dict]) -> tuple[str, str]:
    """Resolve a machines-table `name` to (hostname, ssh-user). Raises if not found."""
    for row in machines:
        if row.get('name') == hosts:
            hostname = row.get('hostname', '').strip() or hosts
            user = row.get('ssh-user', '').strip() or AGENT_SSH_USER
            return hostname, user
    raise PlaybookError(f'unknown host "{hosts}" — not "localhost" and not a name in the machines table')


# ── Flattening (composition + cycle detection) ───────────────────────────────

def _resolve_task(task: dict, machines: list[dict]) -> dict:
    hosts = task['hosts']
    if hosts == 'localhost':
        ssh_host, ssh_user = None, None
    else:
        ssh_host, ssh_user = resolve_remote_host(hosts, machines)
    return {
        'name': task.get('name', ''),
        'hosts': hosts,
        'command': task['command'],
        'oversight': classify_oversight(task),
        'ssh_host': ssh_host,
        'ssh_user': ssh_user,
    }


def flatten(name: str, playbooks: dict[str, dict], machines: list[dict], _stack: tuple[str, ...] = ()) -> list[dict]:
    if name not in playbooks:
        raise PlaybookError(f'unknown playbook "{name}"')
    if name in _stack:
        chain = ' -> '.join((*_stack, name))
        raise PlaybookError(f'cycle detected: {chain}')

    flat: list[dict] = []
    for task in playbooks[name]['tasks']:
        if 'ref' in task:
            flat.extend(flatten(task['ref'], playbooks, machines, (*_stack, name)))
        else:
            flat.append(_resolve_task(task, machines))
    return flat


# ── Review, execution ─────────────────────────────────────────────────────────

def print_review(flat_tasks: list[dict]) -> None:
    print('Plan:')
    for i, t in enumerate(flat_tasks, 1):
        marker = '  [requires oversight]' if t['oversight'] else ''
        label = t['name'] or t['command'].strip().splitlines()[0]
        print(f'  {i}. [{t["hosts"]}] {label}{marker}')
    print()
    # Python buffers stdout when it isn't a tty (piped/redirected output); without
    # an explicit flush here, a subprocess's own writes to the shared fd can appear
    # before this review — silently defeating the "review before execution" guarantee.
    sys.stdout.flush()


def confirm(prompt: str) -> bool:
    sys.stdout.flush()
    return input(f'{prompt} [y/N] ').strip().lower() in ('y', 'yes')


def run_local(command: str) -> subprocess.CompletedProcess:
    sys.stdout.flush()
    return subprocess.run(['bash', '-c', command])


def run_remote(host: str, user: str, command: str) -> subprocess.CompletedProcess:
    sys.stdout.flush()
    return subprocess.run([
        'ssh',
        '-o', 'ConnectTimeout=5',
        '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=no',
        f'{user}@{host}', command,
    ])


def execute(flat_tasks: list[dict], skip_oversight: bool = False) -> int:
    for t in flat_tasks:
        if t['oversight'] and not skip_oversight:
            label = t['name'] or t['command'].strip().splitlines()[0]
            if not confirm(f'Run on {t["hosts"]}: {label}?'):
                print('Skipped by user; stopping.')
                return 1

        if t['ssh_host'] is None:
            result = run_local(t['command'])
        else:
            result = run_remote(t['ssh_host'], t['ssh_user'], t['command'])

        if result.returncode != 0:
            print(f'Step failed on {t["hosts"]} (exit {result.returncode}); stopping.', file=sys.stderr)
            return result.returncode

    return 0


# ── list ──────────────────────────────────────────────────────────────────────

def print_list(playbooks: dict[str, dict]) -> None:
    if not playbooks:
        print('No playbooks found.')
        return
    for pb in sorted(playbooks.values(), key=lambda p: p['name']):
        print(pb['name'])
        if pb['description']:
            print(f'  {pb["description"]}')
        if pb['aliases']:
            print(f'  aliases: {", ".join(pb["aliases"])}')
        print(f'  source: {os.path.basename(pb["source"])}')
        print()


def list_main(argv: list[str]) -> None:
    try:
        playbooks = load_playbooks(get_skills_home())
    except PlaybookError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)
    print_list(playbooks)


PLAYBOOK_SUBCOMMANDS = {'list': list_main}


def playbook_main(argv: list[str]) -> None:
    if not argv or argv[0] not in PLAYBOOK_SUBCOMMANDS:
        print(f'Usage: topology playbook <{"|".join(PLAYBOOK_SUBCOMMANDS)}>', file=sys.stderr)
        sys.exit(1)
    subcommand, rest = argv[0], argv[1:]
    PLAYBOOK_SUBCOMMANDS[subcommand](rest)


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> None:
    skip_oversight = '--skip-oversight' in argv
    phrase = ' '.join(a for a in argv if a != '--skip-oversight').strip()

    if not phrase:
        print('Usage: topology run "<phrase>" [--skip-oversight]', file=sys.stderr)
        sys.exit(1)

    try:
        playbooks = load_playbooks(get_skills_home())
    except PlaybookError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    name = resolve_alias(phrase, playbooks)
    if name is None:
        print(f'No playbook matches "{phrase}".', file=sys.stderr)
        candidates = near_miss_candidates(phrase, playbooks)
        if candidates:
            print('Did you mean:', file=sys.stderr)
            for c in candidates:
                print(f'  - {c}', file=sys.stderr)
        sys.exit(1)

    try:
        flat = flatten(name, playbooks, load_machines_table())
    except PlaybookError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    print_review(flat)
    sys.exit(execute(flat, skip_oversight=skip_oversight))


if __name__ == '__main__':
    main(sys.argv[1:])
