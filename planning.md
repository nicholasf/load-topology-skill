# Planning notes — load-topology / ask-remote-* / track-tasks

## Issues observed

1. **No history/playback.** `command.md` in each skill encodes procedure as prose that
   Claude re-interprets every session (e.g. load-topology `command.md` Step 6: "Offer to
   execute the startup command directly"). Nothing records the actual command that was
   run or its exact invocation shape, so there's nothing to replay — each session
   re-derives the action from the doc, and that derivation drifts across model versions.
   This is the pattern CLAUDE.md already flags: "Prefer building scripted logic in Python
   or other languages rather than building instructions into command.md."

2. **ask-remote-agent is less deterministic than ask-remote-llm.** Structural, not
   incidental. `ask-remote-llm/agent.py` keeps the tool-calling loop local — every tool
   call the model requests is inspected and executed by our code (`run()` in agent.py),
   giving a fixed, auditable execution path. `ask-remote-agent/peer.py` hands the whole
   task to a foreign agent (Hermes/Goose) and only gets back the final text — no
   visibility into what it did, no local validation of intermediate steps. Lower
   determinism is a consequence of that handoff, not a tunable bug.

3. **Tasks hang or finish silently.** No timeout exists at the top level in either
   remote-agent path. `goose/acp.py::_run` loops on `ws.recv()` with no timeout — a
   wedged connection blocks forever. `peer.py::_run_hermes` and `agent.py::make_llm()`
   construct `ChatOpenAI` with no `request_timeout`. `agent.py`'s loop caps at
   `MAX_ITERATIONS=400`, which bounds iteration count, not wall-clock time. There's no
   heartbeat, completion signal, or watchdog — the human is the timeout.

## Ideas under consideration

**A. Rename this library to something more generic and bundle in ask-remote-\*.**
Organizational only — doesn't fix issues 1, 2, or 3 on its own. Main effect: collapses
three `SKILLS_HOME` entries and three `SKILL.md`/dependency declarations into one, and
removes the current `depends_on: load-topology-skill` indirection. Runs opposite to the
direction described in the "I don't even have any good skills" post — splitting a
monorepo into independent, versioned skill repos specifically so they could be
installed/updated separately via `SKILLS_HOME`.

**B. Add a "do" command pattern — record anything in the command for playback.**
Directly addresses issue 1. A wrapper that logs the exact invocation (command string,
args, target host, timestamp) to a file in `$SKILLS_HOME` gives a deterministic replay
source instead of re-deriving from `command.md` each session. Doesn't require touching
ask-remote-*; could live entirely in load-topology-skill (or a small shared module)
since it's the one issuing startup/discover commands today. Doesn't address issue 2 or 3.

**C. Merge the three libraries.**
Same organizational effect as A plus actual code consolidation. Complexity concentrates
in a few spots already visible in the repos:
- `peer.py` and `agent.py` both define a `print_prefixed` and both construct
  `ChatOpenAI` the same way — mergeable.
- `peer.py`'s node/handle resolution and `agent.py`'s SSH/local bridge selection would
  need to become one entry point instead of two `command.md` surfaces.
- load-topology-skill has zero runtime dependencies today; the other two pull in
  `langchain-core`/`langchain-openai`/`websockets` — merging drags that dependency into
  whatever's first in the session (`/load-topology` is described as "the first slash
  command I run").
- None of this complexity touches issue 2's determinism gap — that's inherent to the
  Hermes/Goose autonomous-handoff design, not a merge artifact, and would persist in a
  merged codebase unless the delegation model itself changes.

Also relevant, from the earlier full merge-plan review:
- `ask-foreign-*` → `ask-remote-*` rename never finished — `peer.py`/`agent.py`
  docstrings, both `command.md` titles, both SKILL.md descriptions, and several repo
  links still say `ask-foreign-*`.
- Three separate topology parsers exist today (`sync.parse_table`,
  `discover.parse_full_table`, `peer._topology_node` / `_all_topology_hostnames`), plus
  a fourth in `track-tasks-skill/scripts/create.py`. `topology.md` is a de facto API
  with no shared client library and an unused `schema_version` field.
- The documented sidecar convention (`topology-{skill}.md`) is unused — `discover.py`
  writes `## Model State` / `## Agent State` straight into `topology.md`, and
  `peer.py topology --reasoning-buffer` mutates that same file.

## Net read

- **B** closes issue 1 and doesn't require settling A vs. C first.
- **Issue 3** isn't addressed by any of A/B/C as stated — needs timeout/watchdog logic
  added to `peer.py` and `agent.py` regardless of repo structure.
- **Issue 2** is the hardest of the three since it's a property of local-loop vs.
  remote-autonomous-loop, not a code-organization issue.
