# topology-skill

This will let you begin having conversations with your primary agent (e.g. Claude Code) so that you can ask it to do things on other machines on your network. Use it to fulfil your [JARVIS fantasies](https://en.wikipedia.org/wiki/J.A.R.V.I.S.). It's a building block skill for me that I use with [ask-agent-skill](https://github.com/nicholasf/ask-agent-skill) and [track-tasks-skill](https://github.com/nicholasf/track-tasks-skill) to plan and delegate work with other agents running on other machines.

## How I use it

It's the first slash command I run when I load Claude Code in the terminal. From there I can use it to set up other things on my network. This can include anything from making a database run on another machine, to deploying a codebase or starting an LLM for a particular agent.

## Getting Started

You'll need to decide how to provide information about your network. If you're just taking first steps, use the `manual` provider and enter IP addresses yourself. I use [Tailscale](https://tailscale.com/docs/how-to/quickstart)'s free offering for a VPN (they call it a 'Tailnet'), which I'd recommend for anything beyond a single extra machine.

- **`tailscale`** (default) — `sync` queries Tailscale for hostnames and IPs automatically. Tailscale must be installed and running.
- **`manual`** — you enter IP addresses yourself. No Tailscale required.

If you're using Claude Code, just run `/topology` — if no topology exists yet it will guide you through setup. For any other agent, install the package and call the init subcommand directly:

```bash
pip install -e .   # or: uv pip install -e .
topology init       # or, without installing: python3 -m topology.cli init (with `src` on PYTHONPATH)
```

It asks for your provider choice and, for manual mode, your machine hostnames and IPs. It writes `topology.md` and runs sync automatically. Then follow up with discover to probe each machine:

```
/topology discover
```

This is a home lab tool. It does not try to solve enterprise concerns like multiple SSH identities, key rotation, or multi-tenant access. It assumes you own all the machines, you have set up SSH keys, and you want your agent to know as much about your setup as you do.

---

## Examples

```
/topology
```
Read the topology, show machines and models, start or swap a running model. The day-to-day entry point.

```
/topology discover
```
Probe every node: finds running models, agents, GPU/VRAM, GGUF inventory. Do this at the start of a session.

```
/topology sync
```
Pull fresh Tailscale IPs and online status into `topology.md`. Run after adding a machine or when IPs change.

```
/topology benchmark pond qwen3-coder-30b
```
Measure TTFT and token throughput across three runs; writes results into `topology.md`.

```
/topology show
```
Print the full topology — machines, live state, agent state, and all skill sidecars — in one view.

---

## Subcommands

- [`/topology`](#topology) — read topology, show machines and models, start or swap a model
- [`/topology discover`](#discover) — probe every node for live state, hardware, and agents
- [`/topology sync`](#sync) — refresh IPs and online status from the current provider
- [`/topology benchmark <hostname> <model>`](#benchmark) — measure model throughput and record results
- [`/topology show`](#show) — print full combined topology and all sidecar files
- [`/topology help`](#help) — list all subcommands with a one-line description

---

<a id="discover"></a>
**`/topology discover`**

Probes every machine in the topology over SSH and HTTP. For each node it collects GPU/VRAM, local IP, GGUF inventory, running inference backends (llama-server and Ollama), and configured agent endpoints (Hermes, Goose). Results are written into two sections in `topology.md`:

- `## Live State` — inference backend status and GGUF inventory per node
- `## Agent State` — per-node agent liveness

Run this at the start of a session to get an accurate picture of what is installed and running. The skill's main workflow uses these sections as the primary source for model and agent state.

<a id="topology"></a>
**`/topology`**

Reads `topology.md`, presents the machines table and available models, and lets you start or swap a running model. Use it whenever you want the agent to know what is in your mesh before delegating a workload.

<a id="sync"></a>
**`/topology sync`**

Refreshes the machines table and writes `topology-backup.md` before making any changes. Behaviour depends on the provider set in `topology.md`: Tailscale mode queries `tailscale status` to update IPs and online status; manual mode reads the `local-ip` values you entered and validates the table. Manual columns (role, GPU, VRAM, SSH access) are preserved either way.

<a id="benchmark"></a>
**`/topology benchmark <hostname> <model>`**

Runs the `benchmark` subcommand against a live llama-server on the named host and writes results into the `## LLM Benchmarks` table in `topology.md`.

<a id="show"></a>
**`/topology show`**

Prints `topology.md` and every `topology-*.md` sidecar file in `$SKILLS_HOME` as a single combined view.

<a id="help"></a>
**`/topology help`**

Runs the `help` subcommand and prints usage plus a one-line description for every subcommand.

**First-run sequence**

1. Run `/topology` (Claude Code) or `python3 -m topology.cli init` (any other agent). Choose Tailscale or manual; for manual, enter your machine hostnames and IPs when prompted. `topology.md` is written and synced automatically.
2. Run `/topology discover` to populate live state, hardware details, and agent status.
3. Start llama-server on an LLM Node (the skill will show you the startup command).
4. Run `/topology benchmark <hostname> <model>` to record baseline performance.

**Conventions**

- GGUFs are stored at `~/.local/share/gguf/` on each LLM Node (note per-machine exceptions in the topology).
- `llama-server` (llama.cpp) listens on port `9337`; Ollama listens on port `11434`.
- All LLM Nodes and Mesh Nodes are reachable over SSH as `$AGENT_SSH_USER` with key-based auth.
- Tailscale hostnames are used for SSH and API calls; the machines table keeps both Tailscale and local IPs so the skill degrades gracefully if Tailscale is unavailable.
- **Agent handles:** Refer to a running agent as `<machine>-<llm>-<agent>` — e.g. `pond-qwen-goose`, `pond-qwen-hermes`, `gollum-mistral-hermes`. This makes it unambiguous which machine, model, and agent is acting at any point.

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

**`$SKILLS_HOME`** — see [manage-skills-skill](https://github.com/nicholasf/manage-skills-skill). All topology files live here.

Add these to your `~/.zshrc` or `~/.bashrc`.

### Secrets file

Skills that depend on topology-skill store per-node secrets in `$SKILLS_HOME/.env`. Copy `.env.example` to `$SKILLS_HOME/.env` and fill in values as you add skills to your setup.

The naming convention is `<NODE>_<SERVICE>_<VAR>`. For example, a Hermes bearer token for a node named `pond` is stored as `POND_HERMES_KEY`. The machines table in `topology.md` records the env var name in a skill-specific column (e.g. `hermes_key_env: POND_HERMES_KEY`) so each skill knows where to look without hardcoding node names.

This file is gitignored — it is machine-local and may contain secrets.

## Topology file format

The top of the file is a machines table. Narrative content — notes, startup commands, benchmark results — follows below it.

### Metadata

```
**Schema version:** 1
**Provider:** tailscale
**Last refreshed:** 2026-06-06T10:00:00
```

- `**Provider:**` — `tailscale` (default) or `manual`. Controls how `sync` resolves IPs. Omit to default to `tailscale`.

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

Run `/topology discover` to auto-populate live state for all LLM Nodes. This writes two
sections into `topology.md`:

- `## Live State` — running backends, loaded models, and GGUF inventory per node
- `## Agent State` — liveness of configured agent endpoints (Hermes, Goose, etc.)

You can also add manual sections below the table for startup commands and notes — one named
anchor per model/machine combination (e.g. `### pond — qwen3-coder-30b`). These are preserved
across syncs and discover runs.

### Extending the topology for dependent skills

Each dependent skill writes its own sidecar file — `topology-{skill-name}.md` in `$SKILLS_HOME`.
This keeps `topology.md` clean and prevents skills from interfering with each other's data. See
[Sidecar files](#sidecar-files).

### Network layer

Two providers are supported, controlled by the `**Provider:**` field in the topology metadata:

**`tailscale`** (default when the field is absent)
Machines are reachable by Tailscale hostname anywhere on the mesh — no port forwarding needed. `sync` calls `tailscale status --json` to refresh IPs and online status. The `tailscale-ip` column is updated automatically.

**`manual`**
No mesh software required. You populate the `local-ip` column yourself. When you run `sync`, the skill reads those IPs directly rather than querying any external tool. Useful for plain LAN setups or networks where Tailscale is not available. Add `**Provider:** manual` to the topology metadata block to activate this mode.

## Building and syncing your topology

**First time:** run the init subcommand to create `topology.md` from scratch:

```bash
python3 -m topology.cli init
```

It asks for your provider choice (Tailscale or manual), collects machine entries if needed, and calls sync automatically. Pass `--provider` and `--machines` to skip the prompts:

```bash
python3 -m topology.cli init --provider manual --machines "pond 192.168.86.118,gollum 192.168.86.50"
python3 -m topology.cli init --provider tailscale
```

**Subsequent syncs:** refresh IPs and online status against the current provider:

```bash
python3 -m topology.cli sync
```

Or via the slash command:

```
/topology sync
```

To inspect what Tailscale can see before committing it to a topology:

```bash
python3 -m topology.discover_tailscale
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

## Sidecar files

Dependent skills can write their own data alongside `topology.md` rather than adding columns
to the machines table. The convention is `topology-{skill-name}.md` in `$SKILLS_HOME`:

```
$SKILLS_HOME/topology.md                      # machines table — owned by this skill
$SKILLS_HOME/topology-ask-agent.md            # agent endpoints — owned by that skill
$SKILLS_HOME/topology-live-state.md           # example sidecar from another skill
```

The topology skill's command reads all `topology-*.md` files alongside `topology.md`
and synthesises a unified view. Each skill owns exactly one file and can rewrite it freely
without risking interference with other skills.

## Privacy

`topology.md` and its archives must not be committed to version control. The file contains
hostnames, IP addresses, and SSH usernames. Treat it like Terraform state — it can be
regenerated, and it is nobody else's business.

These patterns cover the main file, sidecars, and the backup:

```
topology.md
topology-*.md
```

If your topology lives in a git repository, verify these patterns are present.

## Future

The flat-file format is intentional for now — simple to write, easy to read, no dependencies. A future version will migrate to SQLite for richer queries, programmatic updates from discovery scripts, and cross-machine state sharing over the Tailscale mesh. The `schema_version` field exists to make that migration detectable and automatic.
