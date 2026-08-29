# topology-skill

Under development.


Topology lets you do things with machines on your network. It could just be your localhost. I wrote it because I run LLMs on two machines in my house. Since then it's usage has widened a little.

... finish this later - get the prototype working.


Steps:

1. Map a topology
   1. localhost
   2. tailscale
   3. manual
2. View your topology
3. Run a command
4. Record a command in a node playbook (localhost, remote machine)



You can record commands as an ordered list of *tasks* — much like a pipeline file — grouped into a named *playbook* and triggered by a natural language phrase: "clean up docker" or "wake pond up". A phrase might resolve to a playbook with one task or a dozen; that's the author's choice, not a rule the tool enforces. Playbooks work standalone on your own machine (`localhost`) with no setup at all. They also extend across every other machine you own once you build a *topology* — a markdown picture of the *nodes* (machines) an agent can reach, by name, either via ssh or on localhost. You can write other skills that build sidecar topology documents, for e.g. [ask-agent-skill](https://github.com/nicholasf/ask-agent-skill), [track-tasks-skill](https://github.com/nicholasf/track-tasks-skill).

This obviously carries security issues about trusting agents on your network and recording sensitive data and application structures in markdown and TOML. All files are prefixed with `topology-` for inclusion in ignore files and patterns. They are about as sensitive as any devops configuration file, so treat them as such.

## How I use it

`/topology load` is the first slash command I run when I load an LLM harness in the terminal. From there I can use it to set up other things on my network, usually other agents and LLMs - sometimes on localhost, sometimes on other nodes. 

This can include anything from making a database run on another machine, to deploying a codebase or starting an LLM for a particular agent.

## Getting Started

The fastest way in is a playbook for your own machine — no topology, no provider, nothing to
discover. Everything past that (reaching other machines, by name) builds on the same idea.

Install the package once:

```bash
pip install -e .   # or: uv pip install -e .
# or, without installing: PYTHONPATH pointed at `src`, e.g. python3 -m topology.cli playbook list
```

### 1. Write a playbook

Playbooks that target `localhost` need no topology at all — `hosts = "localhost"` always means
"the machine running this command," nothing to set up first. Create
`topology-playbook-localhost.toml` in `$TOPOLOGIES_HOME` (default `~/.agents/skills`):

```toml
[[playbook]]
name = "clean-docker"
aliases = ["clean up docker", "prune docker"]
description = "Removes stopped containers, dangling images, and unused volumes."

  [[playbook.tasks]]
  name = "prune"
  hosts = "localhost"
  command = "docker system prune -f"
  oversight = true
```

### 2. Find it, then run it

```
/topology playbook list
```
```
clean-docker
  Removes stopped containers, dangling images, and unused volumes.
  aliases: clean up docker, prune docker
  source: topology-playbook-localhost.toml
```

```
/topology run "clean up docker"
```

Prints the plan, then pauses for confirmation — this task is marked `oversight = true` because
it's destructive. Same phrase works in any future session, on any model: the command doesn't
need to be re-derived from memory or prose again.

That's the whole loop, and it needs nothing but your own machine. See [Playbooks](#playbooks)
for the full format — composing playbooks together, and oversight gating in more depth.
Everything below extends the same `hosts` field and the same playbook format across every other
machine you own.

## Reaching other machines

You'll need to decide how to provide information about your network. If you're just taking
first steps, use the `manual` provider and enter IP addresses yourself. I use
[Tailscale](https://tailscale.com/docs/how-to/quickstart)'s free offering for a VPN (they call
it a 'Tailnet'), which I'd recommend for anything beyond a single extra machine.

- **`tailscale`** (default) — `sync` queries Tailscale for hostnames and IPs automatically. Tailscale must be installed and running.
- **`manual`** — you enter IP addresses yourself. No Tailscale required.

If you're using Claude Code, just run `/topology` — if no topology exists yet it will guide you through setup. For any other agent, call the init subcommand directly:

```bash
topology init       # or: python3 -m topology.cli init
```

It asks for your provider choice and, for manual mode, your machine hostnames and IPs. It writes `topology.toml` and runs sync automatically.

This is a home lab tool. It does not try to solve enterprise concerns like multiple SSH identities, key rotation, or multi-tenant access. It assumes you own all the machines, you have set up SSH keys, and you want your agent to know as much about your setup as you do.

### Identify a node

```
/topology discover
```

Probes every machine over SSH and HTTP — GPU/VRAM, GGUF inventory, running inference backends, agent endpoints — and writes it into `topology.toml`. Run `/topology` afterward to see the machines table and what's running where. Say your topology has a machine named `pond` with an RTX 4090 and no model currently running — that's the node the rest of this section acts on.

### Record a playbook that targets it

Same loop as the localhost example, just pointed at a real host instead:

```toml
[[playbook]]
name = "start-pond-qwen"
aliases = ["start pond's qwen model", "wake pond up"]
description = "Starts llama-server on pond with qwen3-coder-30b loaded."

  [[playbook.tasks]]
  name = "start llama-server"
  hosts = "pond"
  command = '''
  ~/.local/bin/llama-server -m ~/.local/share/gguf/qwen3-coder-30b.gguf --port 9337 &
  '''
```

`hosts = "pond"` is resolved against the machines table, not hardcoded as an IP. `/topology playbook list` and `/topology run "wake pond up"` work exactly as they did for the `localhost` example — same commands, same mental model, just reaching a different machine.

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
Pull fresh Tailscale IPs and online status into `topology.toml`. Run after adding a machine or when IPs change.

```
/topology benchmark pond qwen3-coder-30b
```
Measure TTFT and token throughput across three runs; writes results into `topology.toml`.

```
/topology show
```
Print the full topology — machines, model state, agent state, and all skill sidecars — in one view.

```
/topology run "wake pond up"
```
Resolve a trigger phrase to a playbook, print the full plan, and run it — tasks marked for oversight pause for individual confirmation.

```
/topology playbook list
```
List every playbook — name, description, aliases, source file — across every `topology-playbook*.toml` file.

---

## Subcommands

- [`/topology`](#topology) — read topology, show machines and models, start or swap a model
- [`/topology discover`](#discover) — probe every node for live state, hardware, and agents
- [`/topology sync`](#sync) — refresh IPs and online status from the current provider
- [`/topology benchmark <hostname> <model>`](#benchmark) — measure model throughput and record results
- [`/topology show`](#show) — print full combined topology and all sidecar files
- [`/topology docs`](#docs) — write a per-file markdown breakdown into `$TOPOLOGIES_HOME/README.md`
- [`/topology run "<phrase>"`](#run) — resolve a trigger phrase to a playbook and run it
- [`/topology playbook list`](#playbook-list) — list every playbook: name, description, aliases, source file
- [`/topology help`](#help) — list all subcommands with a one-line description

---

<a id="discover"></a>
**`/topology discover`**

Probes every machine in the topology over SSH and HTTP. For each node it collects GPU/VRAM, local IP, GGUF inventory, running inference backends (llama-server and Ollama), and configured agent endpoints (Hermes, Goose). Results are written into two arrays in `topology.toml`:

- `model_state` — inference backend status, models, context windows, and GGUF inventory per node
- `agent_state` — per-node agent liveness

Run this at the start of a session to get an accurate picture of what is installed and running. The skill's main workflow uses these arrays as the primary source for model and agent state.

<a id="topology"></a>
**`/topology`**

Reads `topology.toml`, presents the machines table and available models, and lets you start or swap a running model. Use it whenever you want the agent to know what is in your mesh before delegating a workload.

<a id="sync"></a>
**`/topology sync`**

Refreshes the machines table and writes `topology-backup.toml` before making any changes. Behaviour depends on the provider set in `topology.toml`: Tailscale mode queries `tailscale status` to update IPs and online status; manual mode reads the `local_ip` values you entered and validates the table. Manual fields (role, GPU, VRAM, SSH access) are preserved either way.

<a id="benchmark"></a>
**`/topology benchmark <hostname> <model>`**

Runs the `benchmark` subcommand against a live llama-server on the named host and writes results into the `benchmarks` array in `topology.toml`.

<a id="show"></a>
**`/topology show`**

Prints `topology.toml` and every `topology-*.toml` sidecar file in `$TOPOLOGIES_HOME` as a single combined view.

<a id="docs"></a>
**`/topology docs`**

Writes a per-file markdown breakdown of `topology.toml` and its sidecar TOML files into
`$TOPOLOGIES_HOME/README.md`, so the repo's own README stays a readable index of what's inside
each file without hand-editing. For every top-level `[[section]]` entry, it lists a short label
(the entry's first field — `name` for machines/playbooks, `hostname` for state/benchmark rows)
and a GitHub line-number link back to the raw TOML (`topology.toml#L12`), so you can jump
straight from the README to the exact line. Output is written between
`<!-- topology-docs:start -->`/`<!-- topology-docs:end -->` markers — re-running it replaces only
that block, leaving the rest of the README (or a first-time file with none yet) untouched.

<a id="run"></a>
**`/topology run "<phrase>"`**

Resolves the phrase against every playbook's aliases (see [Playbooks](#playbooks)), prints the full flattened plan, then runs each task in order, stopping at the first failure. Add `--skip-oversight` to run without pausing for individual task confirmation — the plan still always prints first. Add `--var KEY=VALUE` (repeatable) to fill in `${VAR}` placeholders in task commands.

<a id="playbook-list"></a>
**`/topology playbook list`**

Lists every playbook found across `topology-playbook*.toml` — name, description, aliases, and which file it came from — sorted by name.

<a id="help"></a>
**`/topology help`**

Runs the `help` subcommand and prints usage plus a one-line description for every subcommand.

**First-run sequence**

1. Run `/topology` (Claude Code) or `python3 -m topology.cli init` (any other agent). Choose Tailscale or manual; for manual, enter your machine hostnames and IPs when prompted. `topology.toml` is written and synced automatically.
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

**`$GGUF_PATH`** — path to the directory where GGUF model files are stored. If a machine stores models elsewhere, note the exception in its section of `topology.toml`.

### Environment variables

**`$AGENT_SSH_USER`** — your username across all machines in the mesh. Every LLM Node and Mesh Node must have this user configured with passwordless key-based SSH auth before agents can act on them. An optional `ssh_user` field in the topology table overrides this per machine for the occasional exception.

**`$TOPOLOGIES_HOME`** — where `topology.toml`, sidecar files, and playbooks live. Defaults to `~/.agents/skills` if unset; point it at a git-tracked directory to version your topology and playbooks like any other config.

**`$SKILLS_HOME`** — see [manage-skills-skill](https://github.com/nicholasf/manage-skills-skill). Where installed skill code lives and where dependent skills store their secrets (`.env`) — unrelated to where topology data lives.

Add these to your `~/.zshrc` or `~/.bashrc`.

### Secrets file

Skills that depend on topology-skill store per-node secrets in `$SKILLS_HOME/.env`. Copy `.env.example` to `$SKILLS_HOME/.env` and fill in values as you add skills to your setup.

The naming convention is `<NODE>_<SERVICE>_<VAR>`. For example, a Hermes bearer token for a node named `pond` is stored as `POND_HERMES_KEY`. The machines table in `topology.toml` records the env var name in a skill-specific field (e.g. `hermes_key_env = "POND_HERMES_KEY"`) so each skill knows where to look without hardcoding node names.

This file is gitignored — it is machine-local and may contain secrets.

## Topology file format

`topology.toml` is the source of truth — read and written as TOML (stdlib `tomllib`/a small
hand-rolled writer, same approach as playbooks: no new dependency). `topology show` renders it
as aligned text tables for humans; the raw file itself is the thing every subcommand reads and
writes.

### Metadata

Top-level scalars:

```toml
schema_version = 1
provider = "tailscale"
last_refreshed = "2026-06-06T10-00-00"
```

- `provider` — `"tailscale"` (default) or `"manual"`. Controls how `sync` resolves IPs. Omit to default to `tailscale`.

### Machines table

```toml
[[machines]]
name = "pond"
hostname = "pond"
tailscale_ip = "100.x.x.1"
local_ip = "192.168.x.1"
os = "Ubuntu 24.04 WSL2"
role = "LLM Node, Mesh Node"
ssh = true
gpu = "RTX 4090"
vram = "24GB"
last_verified = "2026-06-01"

[[machines]]
name = "hut"
hostname = "hut"
tailscale_ip = "100.x.x.3"
os = "macOS"
role = "Client"
ssh = true
last_verified = "2026-06-01"
```

A field with nothing to say (`hut` has no `local_ip` or `gpu`) is just omitted — TOML doesn't
require every `[[machines]]` entry to share a schema, so there's no `—` placeholder needed for a
genuinely absent value the way a markdown table would need one.

**Fields:**
- `name` — human-friendly name. There is no rule against warmth here.
- `hostname` — Tailscale hostname, used for SSH and API calls
- `tailscale_ip` — Tailscale IPv4 address; updated by sync
- `local_ip` — LAN IP, maintained manually; useful when Tailscale is unavailable
- `os` — operating system
- `role` — `Client`, `LLM Node`, `Mesh Node`; comma-separated for multiple
- `ssh` — `true`/`false`; whether `$AGENT_SSH_USER` can reach this machine
- `ssh_user` — omit to use `$AGENT_SSH_USER`; set only when the username differs
- `gpu` — GPU model; omit for CPU-only or client machines
- `vram` — VRAM available for inference
- `last_verified` — date you last confirmed this row is accurate

### LLM Node role

An LLM Node is any machine that runs inference workloads. The skill assumes:
- GGUFs stored at `~/.local/share/gguf/` (note this per machine if different)
- `llama-server` (llama.cpp) and/or Ollama are installed
- Port `9337` for llama-server, port `11434` for Ollama

Run `/topology discover` to auto-populate live state for all LLM Nodes. This writes two arrays
into `topology.toml`:

- `model_state` — running backends, loaded models, context windows, and GGUF inventory per node
- `agent_state` — liveness of configured agent endpoints (Hermes, Goose, etc.)

### Extending the topology for dependent skills

Each dependent skill writes its own sidecar file — `topology-{skill-name}.toml` in `$TOPOLOGIES_HOME`.
This keeps `topology.toml` clean and prevents skills from interfering with each other's data. See
[Sidecar files](#sidecar-files).

### Network layer

Two providers are supported, controlled by the `provider` field in the topology metadata:

**`tailscale`** (default when the field is absent)
Machines are reachable by Tailscale hostname anywhere on the mesh — no port forwarding needed. `sync` calls `tailscale status --json` to refresh IPs and online status. The `tailscale_ip` field is updated automatically.

**`manual`**
No mesh software required. You populate the `local_ip` field yourself. When you run `sync`, the skill reads those IPs directly rather than querying any external tool. Useful for plain LAN setups or networks where Tailscale is not available. Set `provider = "manual"` in the topology metadata to activate this mode.

## Building and syncing your topology

**First time:** run the init subcommand to create `topology.toml` from scratch:

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

Dependent skills can write their own data alongside `topology.toml` rather than adding columns
to the machines table. The convention is `topology-{skill-name}.toml` in `$TOPOLOGIES_HOME`:

```
$TOPOLOGIES_HOME/topology.toml                    # machines table — owned by this skill
$TOPOLOGIES_HOME/topology-ask-agent.toml          # agent endpoints — owned by that skill
$TOPOLOGIES_HOME/topology-live-state.toml         # example sidecar from another skill
```

The topology skill's command reads all `topology-*.toml` files alongside `topology.toml`
and synthesises a unified view. Each skill owns exactly one file and can rewrite it freely
without risking interference with other skills.

## Playbooks

A playbook is a named, alias-tagged sequence of commands run against one or more nodes —
recorded once so a phrase resolves to it deterministically later, instead of being re-derived
from prose every session.

Playbooks live in TOML files in `$TOPOLOGIES_HOME`, matched by one glob: `topology-playbook*.toml`.

- `topology-playbook-<node>.toml` — every task in the playbook targets one host (e.g.
  `topology-playbook-pond.toml`), where `<node>` matches a `name` in the machines table.
- `topology-playbooks.toml` — the shared file, for playbooks whose tasks span more than one
  host. A cross-node playbook is built by *composing* single-node playbooks (see below), not
  by writing one alias that implicitly means different things depending on which node it
  touches — resolving which node(s) an action affects is never inferred at run time.

A file can hold more than one playbook, using TOML's array-of-tables:

```toml
[[playbook]]
name = "start-pond-qwen"
aliases = ["start pond's qwen model", "wake pond up"]
description = "Starts llama-server on pond with qwen3.8 loaded."

  [[playbook.tasks]]
  name = "start llama-server"
  hosts = "pond"
  command = '''
  ~/.local/bin/llama-server -m ~/.local/share/gguf/qwen3-coder-30b.gguf --port 9337 &
  '''

  [[playbook.tasks]]
  name = "health check"
  hosts = "pond"
  command = "curl -s http://pond:9337/health"
  oversight = false
```

**Tasks** are deliberately simple — a host and a literal command, plus optional `${VAR}`
placeholders (see [Variables](#run) below); no conditionals or loops. A task is either:

- a **command task** — `hosts` is a `name` from the machines table (resolved to `hostname`/
  `ssh_user` and run over SSH) or the reserved `localhost`, which runs as a local subprocess
  with no SSH and no table lookup — plus `command`, the literal shell command. Use a TOML
  literal string (`'''...'''`) for multi-line commands so the shell text round-trips verbatim,
  backslashes included.
- a **playbook task** — `ref` names another playbook, expanded in place. This is how a
  cross-node playbook is built: define the same intent once per relevant node (e.g.
  `restart-model-server` in both `topology-playbook-pond.toml` and
  `topology-playbook-gollum.toml`, each with node-appropriate commands), then a playbook in
  the shared file composes them via `ref`. A playbook that references itself, directly or
  transitively, is rejected instead of looping.

**Oversight.** Any task can require an individual Y/N confirmation before it runs — set with
`oversight = true`/`false`, or left unset, in which case a keyword heuristic (`restart`,
`kill`, `stop`, `rm`, `drop`, `wipe`) flags a match. An explicit value always wins over the
heuristic, in either direction. The full flattened plan — every task, its host, and whether it
requires oversight — always prints before anything runs, whether or not any individual task is
gated.

**Running a playbook:**

```
/topology run "wake pond up"
```

Matches the phrase against every playbook's `aliases` (exact/normalized string match — no
model involved in resolution or execution), prints the flattened plan, then executes each task
in order, stopping on the first non-zero exit. Add `--skip-oversight` to run without pausing
for individual task confirmation — the plan still always prints first. No match prints the
closest alias candidates instead of guessing:

```
$ /topology run "do something unrelated"
No playbook matches "do something unrelated".
Did you mean:
  - wake pond up
  - start pond's qwen model
```

Alias uniqueness is enforced globally across every `topology-playbook*.toml` file — a
duplicate alias anywhere is a parse-time error naming both playbooks. Avoiding a collision in
the first place is on the author; the tool only detects one.

**Variables.** A task's `command` can reference `${VAR}` or `${VAR:-default}`. Supply values
with repeatable `--var KEY=VALUE` flags:

```
/topology run "start pi agent" --var tmux_session=work
```

Every resolved binding — value plus whether it came from `--var` or a default — is printed
before the plan, so a wrong value is caught by inspection instead of by watching the wrong
thing run:

```
Variables:
  tmux_session = work  (provided)

Plan:
  1. [localhost] start pi in tmux
```

A placeholder with no `--var` value and no default is a hard error before anything runs.

**Finding a playbook again:**

```
/topology playbook list
```

Prints every playbook — name, description, aliases, source file — sorted by name, so you don't have to remember an exact phrase or which file it lives in.

## Privacy

`topology.toml` contains hostnames, IP addresses, SSH usernames, and — via sidecars and
playbooks — what's actually running on each node and how to control it. Treat it like Terraform
state: regenerable, and worth being deliberate about who can see it.

`$TOPOLOGIES_HOME` can point anywhere, including a git repository, so you can version this data
the way you would dotfiles — useful across machines, and lets you diff how your setup changed
over time. If you do that, keep the repo **private**. None of this is a credential (secrets stay
in `$SKILLS_HOME/.env`, never here), but a public repo still hands anyone a recon map of your
home network — real hostnames, IPs, service ports, and exact commands to control them — for no
benefit, since it's specific to your setup rather than reusable by others. If you want to publish
something publicly, write generic template playbooks with placeholder hosts instead of exporting
the real files.

If `$TOPOLOGIES_HOME` is *not* a dedicated repo — e.g. it falls back to `~/.agents/skills`,
shared with other skills — add this to that directory's `.gitignore` so nothing here is
accidentally swept into an unrelated commit:

```
topology.toml
topology-*
```

## Future

The flat-file format is intentional for now — simple to write, easy to read, no dependencies. A future version will migrate to SQLite for richer queries, programmatic updates from discovery scripts, and cross-machine state sharing over the Tailscale mesh. The `schema_version` field exists to make that migration detectable and automatic.
