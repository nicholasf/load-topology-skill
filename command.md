# Load Topology

Reads `$TOPOLOGY_PATH` (default `$SKILLS_HOME/topology.md`, fallback `~/.agents/skills/topology.md`) to enumerate available machines and models, then helps the user start a chosen model or refresh the topology.

## Step 1 — Load the skills env

Before reading the topology, check for `$SKILLS_HOME/.env` and load it if present:

```bash
[ -f "${SKILLS_HOME:-$HOME/.agents/skills}/.env" ] && source "${SKILLS_HOME:-$HOME/.agents/skills}/.env"
```

This file holds secrets and per-node configuration (API keys, URLs) used by skills that depend on this one. It is gitignored and machine-local. See `.env.example` in this repo for the expected format.

## Step 2 — Read the topology file

Resolve the path: `$TOPOLOGY_PATH` → `$SKILLS_HOME/topology.md` → `~/.agents/skills/topology.md`.

If the file does not exist, tell the user and stop. Do not proceed with cached or assumed knowledge.

Read the full file.

## Step 3 — Present the machines table

Display the machines table clearly. Note which machines have `ssh: yes` — these are the ones agents can act on remotely. Note the last-refreshed date if present.

## Step 4 — Present available models and live state

If the topology file contains a `## Model State` section, use it as the primary source — it
reflects the last discover run and shows what is actually installed and running per node,
including the context window for each backend.
Present it as a numbered list:

```
Available models:

  1. qwen3-coder-30b.gguf  on pond    (llama-server / CUDA, port 9337, ctx 65536) — up
  2. qwen3-coder:30b        on gollum  (Ollama / ROCm,       port 11434, ctx 131072) — up
  3. qwen2.5-coder:14b      on gollum  (Ollama / ROCm,       port 11434, ctx 32768) — up
```

If there is no `## Model State` section, fall back to per-node model sections in the file,
or suggest the user run `/load-topology discover` first.

## Step 4b — Present agent state

If the topology file contains an `## Agent State` section, present it alongside the models:

```
Agents:

  pond    hermes  http://pond:8642  — up   (process: running)
  pond    goose   ws://pond:3284    — down (process: not found)
```

Also check for any `topology-*.md` sidecar files in `$SKILLS_HOME` — these are written by
dependent skills (e.g. ask-foreign-agent). Read and summarise any that are present.

## Step 5 — Verify live state if needed

If the user wants a fresh live check beyond what `## Live State` shows, run:

```bash
curl -s http://<hostname>:9337/v1/models
```

or:

```bash
ssh $AGENT_SSH_USER@<hostname> "pgrep -a llama-server"
```

Report the result.

## Step 6 — Start a model

Ask the user which model they want to load (or confirm the current one is fine).

Find the named anchor for their choice (e.g. `### gollum — qwen3-coder-30b`) and display the startup command.

If swapping models, remind the user to kill the existing process first:

```bash
ssh $AGENT_SSH_USER@<hostname> "pkill -f llama-server"
```

Offer to execute the startup command directly if the user confirms.

## Step 7 — Confirm the model is live

After starting, verify:

```bash
curl -s http://<hostname>:9337/v1/models
```

Report the model name returned. The model is ready when this returns a valid JSON response.

## Step 8 — Hand off

Inform the user which machine and model are active, the API endpoint (e.g. `http://gollum:9337`), and that tasks can now be delegated using the **track-tasks-skill**.

---

## Discover subcommand

When the user says `/load-topology discover` or "discover topology" or "probe nodes":

1. Run:
   ```bash
   python3 "${SKILLS_HOME:-$HOME/.agents/skills}/load-topology-skill/scripts/discover.py"
   ```

2. The script probes every machine in the machines table:
   - HTTP: llama-server (:9337) and Ollama (:11434) for running models
   - SSH: gpu, vram, local-ip, GGUF inventory at `~/.local/share/gguf/`
   - HTTP: configured agent endpoints (`hermes_gateway`, `goose_acp_url` columns)
   - SSH: pgrep scan for known agent processes (hermes, goose, aider)

3. It writes two sections into `topology.md`:
   - `## Model State` — inference backend status, models, context windows, and GGUF inventory per node
   - `## Agent State` — per-node agent liveness and `reasoning_buffer` (preserved from prior runs)

4. Re-read the topology file and present the updated `## Model State` and `## Agent State`
   tables to the user.

Run discover at the start of a session whenever you need an accurate picture of what is
actually installed and running, rather than relying on a stale topology.

---

## Sync subcommand

When the user says `/load-topology sync` or "sync topology" or "refresh topology":

1. Run:
   ```bash
   python3 "${SKILLS_HOME:-$HOME/.agents/skills}/load-topology-skill/scripts/sync.py"
   ```
2. Report a summary of changes (new machines added, IPs updated, machines marked offline).
   A single `topology-backup.md` is written before any changes.
3. Re-read the updated topology file and present the refreshed machines table.

---

## Benchmark subcommand

When the user says `/load-topology benchmark <hostname> <model>` or "benchmark llm":

1. Confirm the model is reachable:
   ```bash
   curl -s http://<hostname>:9337/v1/models
   ```
   Stop and report if the server is not responding.

2. Run the benchmark script:
   ```bash
   python3 "${SKILLS_HOME:-$HOME/.agents/skills}/load-topology-skill/scripts/benchmark_llm.py" \
     <hostname> <model> [--port 9337] [--runs 3]
   ```
   Default is 3 runs. The script streams a fixed prompt, measures TTFT (time to first token) and
   generation throughput (tok/s), averages across runs, then writes an `## LLM Benchmarks` table
   into the topology file.

3. Report the results:
   ```
   gollum / qwen3-coder-30b:  ttft=312ms  tok/s=46.8  (avg of 3 runs)
   ```

4. Re-read the topology file and show the updated `## LLM Benchmarks` table so the user can
   see the new entry alongside any prior results.

---

## Show subcommand

When the user says `/load-topology show` or "show topology" or "show all topology files":

1. Run:
   ```bash
   python3 "${SKILLS_HOME:-$HOME/.agents/skills}/load-topology-skill/scripts/show.py"
   ```

2. The script reads `topology.md` followed by every `topology-*.md` sidecar file in
   `$SKILLS_HOME`, printing them in sequence separated by a divider.

3. Present the combined output to the user. Highlight any sidecar files found so it is
   clear which skill owns which data.

Use this when the user wants a full picture of all topology data in one view — machines
table, live state, agent state, and any skill-specific sidecars — without running a
fresh probe.

---

## Notes

- The topology file is the source of truth. Always read it fresh — do not rely on cached knowledge.
- Model state is ephemeral. The topology records installed capacity; always check what is actually running before assuming.
- If the user asks about mesh-llm or multi-node tensor-split, refer them to the mesh-llm sections of the topology file.

---

## Topology extension convention

Skills that depend on `load-topology-skill` may add columns to the topology
table to record their own per-node configuration. The base table covers
hostnames, IPs, SSH access, and model availability. Dependent skills extend it
as needed — for example:

| skill | section | columns added |
|---|---|---|
| `ask-foreign-agent-skill` | machines table | `hermes_gateway`, `hermes_key_env` |
| `ask-remote-agent-skill` | `## Agent State` | `reasoning_buffer` |

`hermes_gateway` is the HTTP URL of the Hermes agent server on that node (e.g.
`http://pond:8642`). `hermes_key_env` is the name of the env var in
`$SKILLS_HOME/.env` that holds the Bearer token for that gateway (e.g.
`POND_HERMES_KEY`).

`reasoning_buffer` is the estimated token overhead for the model's chain-of-thought
reasoning before it writes output (e.g. `12000` for Qwen3 with thinking enabled,
`0` for models without extended thinking). It is set via the `topology` subcommand
of `ask-remote-agent-skill` and preserved across `discover` runs.

Any skill can follow this pattern: add columns to `topology.md` for structural
config, put secrets in `$SKILLS_HOME/.env` under a predictable name, and
reference the env var name in the table so the skill knows where to look.
