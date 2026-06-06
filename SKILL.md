---
name: load-topology
description: Read the local system topology to discover available machines and models. Use when the user wants to see what machines are available, what models can be run, load a model on a machine, refresh the topology, or prepare for task delegation. Triggers on "load topology", "what models are available", "which machines are running", "start a model", "load a model on", "show me the topology", "refresh topology".
---

# Load Topology

Reads `$TOPOLOGY_PATH` (default `$SKILLS_HOME/topology.md`, fallback `~/.agents/skills/topology.md`) to enumerate available machines and models, then helps the user start a chosen model or refresh the topology.

## Step 1 — Read the topology file

Resolve the path: `$TOPOLOGY_PATH` → `$SKILLS_HOME/topology.md` → `~/.agents/skills/topology.md`.

If the file does not exist, tell the user and stop. Do not proceed with cached or assumed knowledge.

Read the full file.

## Step 2 — Present the machines table

Display the machines table clearly. Note which machines have `ssh: yes` — these are the ones agents can act on remotely. Note the schema version and last-refreshed date if present.

## Step 3 — Present available models

For each LLM Node, locate its models table. Present all available models as a numbered list:

```
Available models:

  1. qwen3-coder-30b   on pond    (llama-server / CUDA,  port 9337, ~215 t/s)
  2. qwen2.5-coder-32b on pond    (llama-server / CUDA,  port 9337, ~30 t/s)
  3. qwen3-coder-30b   on gollum  (llama-server / ROCm,  port 9337)
```

Note any `last-running` entries so the user can see what was most recently active.

## Step 4 — Check what is currently running (optional)

If the user wants a live check, run:

```bash
curl -s http://<hostname>:9337/v1/models
```

or:

```bash
ssh $SSH_USER@<hostname> "pgrep -a llama-server"
```

Report the result.

## Step 5 — Start a model

Ask the user which model they want to load (or confirm the current one is fine).

Find the named anchor for their choice (e.g. `### pond — qwen3-coder-30b`) and display the startup command.

If swapping models, remind the user to kill the existing process first:

```bash
ssh $SSH_USER@<hostname> "pkill -f llama-server"
```

Offer to execute the startup command directly if the user confirms.

## Step 6 — Confirm the model is live

After starting, verify:

```bash
curl -s http://<hostname>:9337/v1/models
```

Report the model name returned. The model is ready when this returns a valid JSON response.

## Step 7 — Hand off

Inform the user which machine and model are active, the API endpoint (e.g. `http://pond:9337`), and that tasks can now be delegated using the **track-tasks-skill**.

---

## Refresh command

When the user says `/load-topology refresh` or "refresh topology":

1. Run:
   ```bash
   python3 "${SKILLS_HOME:-$HOME/.agents/skills}/load-topology-skill/scripts/refresh_topology.py"
   ```
2. Report the archive path and a summary of changes (new machines added, IPs updated).
3. Re-read the updated topology file and present the refreshed machines table.

---

## Notes

- The topology file is the source of truth. Always read it fresh — do not rely on cached knowledge.
- Live model state is ephemeral. The topology records installed capacity; always check what is actually running before assuming.
- If the user asks about mesh-llm or multi-node tensor-split, refer them to the mesh-llm sections of the topology file.
