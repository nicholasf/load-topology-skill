#!/usr/bin/env python3
"""
help.py — print usage and a summary of all load-topology subcommands.

Invoked via: /load-topology help
"""

SUMMARY = 'Read the local system topology to discover available machines and models.'

SUBCOMMANDS = [
    ('(none)', 'Read topology, show machines and models, start or swap a model.'),
    ('discover', 'Probe every node for live state, hardware, and agents.'),
    ('sync', 'Refresh IPs and online status from the current provider.'),
    ('benchmark <hostname> <model>', 'Measure model throughput and record results.'),
    ('show', 'Print full combined topology and all sidecar files.'),
    ('help', 'Show this help message.'),
]


def build_help_text() -> str:
    lines = [SUMMARY, '', 'Usage: /load-topology [subcommand]', '', 'Subcommands:']
    width = max(len(usage) for usage, _ in SUBCOMMANDS)
    for usage, description in SUBCOMMANDS:
        lines.append(f'  {usage.ljust(width)}  {description}')
    return '\n'.join(lines)


def main() -> None:
    print(build_help_text())


if __name__ == '__main__':
    main()
