# load-topology-skill

This will let you begin having conversations with your primary agent so you can ask it to get other agents to do things for you.

This is a skill which relies on some [prerequisites](#prerequisites) to then let an agent coordinate with other ones. I use it with [track-tasks](https://github.com/nicholasf/track-tasks-skill) and [ask-foreign-agent](https://github.com/nicholasf/ask-foreign-agent-skill) to assign workloads to different LLM nodes in my home network. If you use [manage-skills](https://github.com/nicholasf/manage-skills-skill) it will help you set all of these up and autoload them whenever you start a session with your agent.

This is a home lab tool. It does not try to solve enterprise concerns like multiple SSH identities, key rotation, or multi-tenant access. It assumes you own all the machines, you have set up SSH keys, and you want your agent to know as much about your setup as you do.

## Getting started

Once the [prerequisites](#prerequisites) are in place, the skill works through three commands in Claude Code.

**Sync the topology**

```
/load-topology sync
```

Runs `scripts/sync.py`, which queries Tailscale for current IPs and online status, archives the previous file as `YYYY-MM-DDTHH-MM-SS-topology.md` in the same directory, and rewrites the machines table in place. Manual columns (role, GPU, VRAM, SSH access) are preserved. Run this after adding a machine or when IPs have changed.


**Read the topology**

Use this at the start of each session or when you want your agent to begin working with others locally.

```
/load-topology
```

Reads `topology.md`, presents the machines table and available models, and lets you start or swap a running model. This is the day-to-day entry point — use it whenever you want the agent to know what is in your mesh before delegating a workload.

**Benchmark a model**

```
/load-topology benchmark <hostname> <model>
```

Runs `scripts/benchmark_llm.py` against a live llama-server on the named host, measures TTFT and token throughput across three runs, and writes the results into the `## LLM Benchmarks` table in `topology.md`. Run this after loading a new GGUF so the results live alongside the rest of the node's data.

**Populating topology.md for the first time**

The typical first-run sequence is:

1. Copy the [example topology format](#topology-file-format) and fill in your machines manually.
2. Run `/load-topology sync` to pull in live Tailscale IPs and mark machines online or offline.
3. Start llama-server on an LLM Node (the skill will show you the startup command).
4. Run `/load-topology benchmark <hostname> <model>` to record baseline performance.

**Conventions assumed**

- GGUFs are stored at `~/.local/share/gguf/` on each LLM Node (note per-machine exceptions in the topology).
- `llama-server` (llama.cpp) listens on port `9337`; Ollama listens on port `11434`.
- All LLM Nodes and Mesh Nodes are reachable over SSH as `$AGENT_SSH_USER` with key-based auth.
- Tailscale hostnames are used for SSH and API calls; the machines table keeps both Tailscale and local IPs so the skill degrades gracefully if Tailscale is unavailable.

## Prerequisites

### Software

Each LLM Node needs at least one inference backend installed:

- **[llama.cpp](https://github.com/ggerganov/llama.cpp)** — provides `llama-server`, the primary backend. Listens on port `9337` by convention.
- **[Ollama](https://ollama.com)** — alternative backend. Listens on port `11434`.

### GGUF storage

The skill assumes GGUFs live at `~/.local/share/gguf/` on each LLM Node. Set `$GGUF_PATH` to override this default:

**`$GGUF_PATH`** — path to the directory where GGUF model files are stored. If a machine stores models elsewhere, note the exception in its section of `topology.md`.

### Environment variables

**`$AGENT_SSH_USER`** — your username across all machines in the mesh. Every LLM Node and Mesh Node must have this user configured with passwordless key-based SSH auth before agents can act on them. An optional `ssh-user` column in the topology table overrides this per machine for the occasional exception.

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
- `tailscale-ip` — Tailscale IPv4 address; updated by sync
- `local-ip` — LAN IP, maintained manually; useful when Tailscale is unavailable
- `os` — operating system
- `role` — `Client`, `LLM Node`, `Mesh Node`; comma-separated for multiple
- `ssh` — `yes` or `no`; whether `$AGENT_SSH_USER` can reach this machine
- `ssh-user` — leave blank to use `$AGENT_SSH_USER`; fill in only when the username differs
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

## Building and syncing your topology

Use `scripts/discover_tailscale.py` to list machines visible on your Tailscale mesh:

```bash
python3 scripts/discover_tailscale.py
```

This gives you the raw material — hostnames, IPs, online status — to fill in the machines table. Manual columns (name, role, GPU, VRAM, SSH access) are filled in by you.

To sync an existing topology with current Tailscale data:

```bash
python3 scripts/sync.py
```

This archives the current file as `YYYY-MM-DDTHH-MM-SS-topology.md` in the same directory, then rebuilds the machines table from fresh discovery data, preserving all manually-maintained columns.

Or use the slash command in Claude Code:

```
/load-topology sync
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
