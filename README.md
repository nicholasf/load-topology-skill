# load-topology-skill

This skill will let you ask an agent to do things with other machines on your network, including other agents. Get down! 

For a home lab power user with a few machines on a personal network, knowing what you have is fundamental to getting anything done with agents. This skill formalises that knowledge as a topology file — a structured record of your machines, their roles, the models they run, and how to reach them — so agents can read it, reason about it, and act.

This is a home lab tool. It does not try to solve enterprise concerns like multiple SSH identities, key rotation, or multi-tenant access. It assumes you own all the machines, you have set up SSH keys, and you want your agent to know as much about your setup as you do.

## Prerequisites

Three environment variables are expected:

**`$SSH_USER`** — your username across all machines in the mesh. Every LLM Node and Mesh Node must have this user configured with passwordless key-based SSH auth before agents can act on them. An optional `ssh-user` column in the topology table overrides this per machine for the occasional exception.

**`$TOPOLOGY_PATH`** — path to your `topology.md` file. Default: `$SKILLS_HOME/topology.md`. Keep this outside any git repository — see [Privacy](#privacy).

**`$SKILLS_HOME`** — see [manage-skills-skill](https://github.com/nicholasf/manage-skills-skill).

Add these to your `~/.zshrc` or `~/.bashrc`.

## Topology file format

The top of the file is a machines table. Narrative content — notes, startup commands, benchmark results — follows below it.

### Metadata

```
**Schema version:** 1
**Last refreshed:** 2026-06-06T10:00:00
```

### Machines table

| name | hostname | tailscale-ip | local-ip | os | role | ssh | ssh-user | gpu | vram | last-verified |
|------|----------|--------------|----------|----|------|-----|----------|-----|------|---------------|
| pond | pond | 100.x.x.1 | 192.168.x.1 | Ubuntu 24.04 WSL2 | LLM Node, Mesh Node | yes | | RTX 4090 | 24GB | 2026-06-01 |
| gollum | gollum | 100.x.x.2 | 192.168.x.2 | Fedora 42 | LLM Node, Mesh Node | yes | | Radeon 780M | 15.8GB UMA | 2026-06-01 |
| hut | hut | 100.x.x.3 | | macOS | Client | yes | | — | — | 2026-06-01 |

**Columns:**
- `name` — human-friendly name. There is no rule against warmth here.
- `hostname` — Tailscale hostname, used for SSH and API calls
- `tailscale-ip` — Tailscale IPv4 address; updated by refresh
- `local-ip` — LAN IP, maintained manually; useful when Tailscale is unavailable
- `os` — operating system
- `role` — `Client`, `LLM Node`, `Mesh Node`; comma-separated for multiple
- `ssh` — `yes` or `no`; whether `$SSH_USER` can reach this machine
- `ssh-user` — leave blank to use `$SSH_USER`; fill in only when the username differs
- `gpu` — GPU model, or `—` for CPU-only or client machines
- `vram` — VRAM available for inference
- `last-verified` — date you last confirmed this row is accurate

### LLM Node role

An LLM Node is any machine that runs inference workloads. The skill assumes:
- GGUFs stored at `~/.local/share/gguf/` (note this per machine if different)
- `llama-server` (llama.cpp) and/or Ollama are installed
- Port `9337` for llama-server, port `11434` for Ollama

For each LLM Node, add a section below the table with:
- A models table: model name, size, quantisation, backend, port, last-running
- Startup commands (one named anchor per model/machine combination)
- Benchmark results table

The `last-running` note per model records the last time a model was confirmed live — keeping live state out of the primary table, which describes installed capacity only.

### Network layer

The reference implementation uses Tailscale — machines are reachable by hostname anywhere on the mesh, no port forwarding needed. The discovery script and topology format are network-agnostic; another provider (ZeroTier, plain SSH config) can be substituted.

## Building and refreshing your topology

Use `scripts/discover_tailscale.py` to list machines visible on your Tailscale mesh:

```bash
python3 scripts/discover_tailscale.py
```

This gives you the raw material — hostnames, IPs, online status — to fill in the machines table. Manual columns (name, role, GPU, VRAM, SSH access) are filled in by you.

To refresh an existing topology with current Tailscale data:

```bash
python3 scripts/refresh_topology.py
```

This archives the current file as `YYYY-MM-DDTHH-MM-SS-topology.md` in the same directory, then rebuilds the machines table from fresh discovery data, preserving all manually-maintained columns.

Or use the slash command in Claude Code:

```
/load-topology refresh
```

## Benchmark suite

Run these tests against each LLM Node when setting up a new model or comparing backends. Record results in the benchmark table below each node's section.

All tests use the same API call pattern — swap the endpoint and model name for llama-server vs Ollama.

### Simple

| Language | Prompt |
|----------|--------|
| Go | Write a fibonacci function in Go |
| Python | Write a fibonacci function in Python |
| React | Write a React counter component with increment and decrement buttons |

### Complex

| Language | Prompt |
|----------|--------|
| Go | Write a Go HTTP middleware that logs request duration and returns 429 if requests exceed 100 per minute per IP |
| Python | Write a FastAPI middleware that logs request duration and returns 429 if requests exceed 100 per minute per IP |
| React | Write a React component that fetches paginated data from an API, displays it in a table, and handles loading and error states |

### Reasoning

| Language | Prompt |
|----------|--------|
| Go | What are the tradeoffs between using GORM and sqlc in a Go service? |
| Python | What are the tradeoffs between using SQLAlchemy ORM and raw SQL with psycopg2 in a Python service? |
| React | What are the tradeoffs between Redux and Zustand for state management in a React application? |

**Metrics to record:** date, backend, model, test, language, total time, token count, gen t/s, prompt t/s, processor.

## Privacy

`topology.md` and its archives must not be committed to version control. The file contains hostnames, IP addresses, and SSH usernames. Treat it like Terraform state — it can be regenerated, and it is nobody else's business.

Both patterns are in `.gitignore`:

```
topology.md
*-topology.md
```

If your topology lives in a git repository, verify these patterns are present.

## Future

The flat-file format is intentional for now — simple to write, easy to read, no dependencies. A future version will migrate to SQLite for richer queries, programmatic updates from discovery scripts, and cross-machine state sharing over the Tailscale mesh. The `schema_version` field exists to make that migration detectable and automatic.
