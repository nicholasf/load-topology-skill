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

## Step 4 — Present available models

For each LLM Node, locate its models table. Present all available models as a numbered list:

```
Available models:

  1. qwen3-coder-30b   on gollum  (llama-server / ROCm,  port 9337)
  2. qwen2.5-coder-32b on gollum  (llama-server / ROCm,  port 9337)
```

Note any `last-running` entries so the user can see what was most recently active.

## Step 5 — Check what is currently running (optional)

If the user wants a live check, run:

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

## Sync subcommand

When the user says `/load-topology sync` or "sync topology" or "refresh topology":

1. Run:
   ```bash
   python3 "${SKILLS_HOME:-$HOME/.agents/skills}/load-topology-skill/scripts/sync.py"
   ```
2. Report the archive path and a summary of changes (new machines added, IPs updated, machines marked offline).
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

## Notes

- The topology file is the source of truth. Always read it fresh — do not rely on cached knowledge.
- Live model state is ephemeral. The topology records installed capacity; always check what is actually running before assuming.
- If the user asks about mesh-llm or multi-node tensor-split, refer them to the mesh-llm sections of the topology file.

---

## Topology extension convention

Skills that depend on `load-topology-skill` may add columns to the topology
table to record their own per-node configuration. The base table covers
hostnames, IPs, SSH access, and model availability. Dependent skills extend it
as needed — for example:

| skill | columns added |
|---|---|
| `ask-foreign-agent-skill` | `hermes_gateway`, `hermes_key_env` |

`hermes_gateway` is the HTTP URL of the Hermes agent server on that node (e.g.
`http://pond:8642`). `hermes_key_env` is the name of the env var in
`$SKILLS_HOME/.env` that holds the Bearer token for that gateway (e.g.
`POND_HERMES_KEY`).

Any skill can follow this pattern: add columns to `topology.md` for structural
config, put secrets in `$SKILLS_HOME/.env` under a predictable name, and
reference the env var name in the table so the skill knows where to look.
