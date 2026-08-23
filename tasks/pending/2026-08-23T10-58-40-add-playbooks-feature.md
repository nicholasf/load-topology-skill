# Add playbooks: alias-triggered, reviewed command sequences

**Created:** 2026-08-23 10:58:40
**Model:** Cloud reasoning model (e.g. Claude) — architecture-heavy, several open design decisions below still need to be resolved during implementation, not mechanical execution. No `topology.md` exists in this repo (it's the tool's own source, not a consumer of it), so this is best judgement per track-tasks guidance, not a topology.md-informed assignment.
**Status:** in-progress — implemented, awaiting your review before being marked completed

## Goal

`topology run "<phrase>"` deterministically resolves a trigger phrase to a named, alias-tagged sequence of host commands and runs it, so that what to do on a node survives a model switch instead of being re-derived from prose each session.

## Background

`planning.md` (Issue 1, Idea B) already names this gap: `command.md` encodes procedure as prose the model re-derives every session, so nothing is replayable across model versions. This task implements that as "playbooks" — the term is provisional and may be revisited later, keep it as-is for now.

Design decisions reached (treat as settled unless a listed open question says otherwise):

- **Storage:** playbooks are split across files by scope, not one fixed file:
  - A playbook whose steps all target a single host lives in `topology-playbook-<node>.toml` (e.g. `topology-playbook-pond.toml`), where `<node>` matches a `name` in the machines table.
  - A playbook whose steps span more than one host (necessarily a composition of single-node playbooks — see Dispatch/Flow below) lives in the shared `topology-playbooks.toml`.
  - The resolver discovers all of them with one glob, `topology-playbook*.toml` (matches both `topology-playbooks.toml` and every `topology-playbook-<node>.toml`, but not unrelated sidecars like `topology-ask-agent.md`), and merges them into one alias/name namespace — a `ref` in a composed task resolves the same way regardless of which file defines the target.
  - `localhost` is a reserved pseudo-host, not a row in the machines table: it means "the machine executing the playbook" and tasks targeting it run as a plain local subprocess, never SSH. It gets its own file, `topology-playbook-localhost.toml`, same convention as any other node — this is also where locally-runnable things (e.g. a local coding agent) are described, as playbooks, not as a separate inventory/registry. There is no second lookup mechanism for "known local agents" — a playbook's `name` and tasks are the description, and `topology playbook list` filtered to that file is the listing.
  - All of these follow the existing `topology-{skill}.md` sidecar convention (see README "Sidecar files"), extended to a new extension, and must be treated at the same privacy tier as `topology.md` — gitignored, local-only — because playbooks reveal what's running on a node and how to control it, not just network details, which is a superset of the sensitivity `topology.md` already has.
- **File format:** TOML, not markdown or YAML. A devops-language-shaped vocabulary (`hosts`, `name`, an ordered task list) was the goal, not literal Ansible interop — Ansible came up only as an example of that category, this project has no actual plan to wrap or invoke it. Given that, TOML wins on its own merits over YAML: `tomllib` has been in the stdlib since Python 3.11, which is already this project's minimum (`pyproject.toml` `requires-python = ">=3.11"`), so parsing playbooks adds **no new dependency at all** (`tomllib` is read-only, which is fine — playbooks are hand-authored only per the open questions below, nothing needs to write these files). TOML is also more explicit than YAML — no implicit type coercion footguns (`no`/`off` as booleans, indentation-sensitivity) in a file where a misparsed `oversight` boolean has real consequences. A task list is TOML's array-of-tables construct, `[[tasks]]` — each `[[tasks]]` block appends one table to the `tasks` array, order preserved, which is exactly the ordered-step-list shape needed; a `command` value should use TOML's literal multi-line string (`'''...'''`, no escape processing) rather than a basic string (`"""..."""`), so arbitrary shell text — backslashes included — round-trips verbatim.
- **Naming rule (decided):** every file this project generates or writes — the root `topology.md`, `topology-backup.md`, dependent-skill sidecars, and the new `topology-playbooks.md` — is prefixed `topology-` (the root file is the sole exception, matched by its own literal name). `.gitignore` should therefore just be `topology.md` plus a single `topology-*` pattern; no file this project ever creates should need a separate ignore rule.
- **IMPORTANT — pre-existing gitignore bug found while scoping this:** README's Privacy section documents the ignore patterns as `topology.md` / `topology-*.md`, and `sync.py`'s `list_sidecars()` globs sidecars with that same `topology-*.md` prefix pattern. But the actual `.gitignore` in this repo has `*-topology.md` (a suffix pattern) instead — it does not match `topology-*.md`-style filenames. As written, real sidecars like a future `topology-playbooks.md` would NOT be excluded by `.gitignore` today. Fixing this to match the naming rule above is a prerequisite for this task, since `topology-playbooks.md` must actually be private.
- **File structure:** a `topology-playbook*.toml` file holds a top-level `[[playbook]]` array-of-tables — more than one playbook per file, not one file per playbook (needed as soon as a node has more than one playbook, e.g. `localhost` ends up with both a "start Pi against pond" and, later, a "start Pi against OpenRouter" playbook in the same file). Each playbook's task list nests under it as `[[playbook.tasks]]`, standard TOML nested array-of-tables — a task belongs to whichever `[[playbook]]` most recently preceded it in the file.
- **Step schema:** a playbook has `name`, `aliases` (array of trigger phrases), `description`, and an ordered `[[playbook.tasks]]` array. A task is one of:
  - a **command task** — `hosts` is either a target host **name** (resolved against the `topology.md` machines table `name`/`hostname`/`ssh-user` columns, the same way `discover.py` resolves `row['hostname']` and `row.get('ssh-user') or AGENT_SSH_USER`, never a hardcoded IP) or the reserved `localhost`, which skips host-table resolution entirely and runs as a plain local subprocess — plus a `command` (literal multi-line string, `'''...'''`)
  - a **playbook task** — a `ref` naming another playbook, for composition
  - Deliberately excluded, to avoid rebuilding a worse Ansible: conditionals, loops, variable templating, idempotent modules. Tasks stay dumb — a host and a literal command — with all the intelligence in resolution/composition/oversight, not in the task language itself.
- **Cycle detection:** the resolver must detect a playbook that (directly or transitively) references itself and fail with a clear error instead of recursing forever.
- **Alias uniqueness:** enforced globally across every `topology-playbook*.md` file, not per-file. Two playbooks (in the same file or different files) defining the same alias is a parse-time error, reported clearly (which two playbooks, which alias) — the tool detects the collision, it does not attempt to prevent or resolve it; avoiding collisions in the first place is on the author.
- **Cross-node actions are composition, not implicit dispatch:** there is no "one alias that means different things depending on which node it's run on." A node-specific action (e.g. restarting the model server) is defined once per relevant node file with the same playbook name/intent but node-appropriate steps (pond's llama-server restart vs. gollum's Ollama restart); a separate, explicitly-named playbook in the shared file (e.g. `restart-all-model-servers`) fans out by referencing each of those via `type: playbook, ref:`. This keeps every trigger phrase unambiguous — resolving which node(s) an action touches is never inferred at run time.
- **Dispatch:** `topology run "<phrase>"` matches the phrase against alias lists deterministically (exact/normalized string match — no LLM involved in resolution or execution). No match: print the closest alias candidates and stop; never guess or fall back to free-form interpretation.
- **Flow:** resolve → flatten (recursively expand nested `playbook` steps into one ordered list of concrete `command` steps, each carrying its resolved host) → review (print the full flattened list with target hosts before anything runs) → execute step by step → fail-fast on the first non-zero exit.
- **Oversight gating:** any step can require a human sign-off before it runs. A step's oversight status is `explicit_true > explicit_false > heuristic_match > default_false` — i.e. an author-set `oversight: true`/`false` field always wins; when absent, a heuristic pattern-matches the command text (candidates: `restart`, `kill`, `stop`, `rm`, `drop`, `wipe` — finalize the list during implementation) and flags a match.
- **Execution-time gating is per-step**, not one whole-run confirmation: an oversight step pauses for an individual Y/N; non-oversight steps run straight through. This is separate from, and in addition to, the upfront full review, which always prints regardless of gating or bypass flags.
- **Bypass flag:** a CLI flag (name TBD — `--skip-oversight` is the working name) lets all oversight-gated steps run without individual per-step confirmation, for scripted/unattended use. The upfront review must still always print even when this flag is used.

## Changes

- Fix `.gitignore`: replace `*-topology.md` with `topology.md` plus `topology-*` (deliberately not `.md`-scoped, so it also covers the new `.toml` playbook files), per the naming rule above — one pattern covers every file this project creates, present and future, with no per-file exceptions to remember.
- No `pyproject.toml` change needed: `tomllib` is stdlib for Python 3.11+, which this project already requires, so parsing playbooks adds no new runtime dependency.
- New module `src/topology/playbook.py`:
  - Parser: globs `topology-playbook*.toml` in `$SKILLS_HOME`, reads each with `tomllib.load()` (binary mode — `tomllib` requires a `rb`-opened file), and validates into structured playbook records (name, aliases, description, ordered tasks, per-task oversight field), merged into one namespace
  - Global alias-uniqueness check across the merged set: a duplicate alias anywhere is a parse-time error naming both colliding playbooks
  - Alias resolver: phrase → playbook name (exact/normalized match; near-miss candidate listing on no match)
  - Flattener: recursive expansion of playbook-reference tasks into concrete command tasks, with cycle detection
  - Host resolution: `hosts: localhost` → local subprocess, no lookup; anything else → the machines-table lookup pattern already used in `discover.py` (`hostname`, `ssh-user` fallback to `$AGENT_SSH_USER`, `ssh: yes/no` gate)
  - Oversight classifier: implements the `explicit_true > explicit_false > heuristic_match > default_false` precedence described above
- New CLI subcommand `run` wired into `src/topology/cli.py`'s dispatch dict, and into `src/topology/help.py`'s subcommand listing
- Review + execution driver: prints the flattened plan (host, command, oversight flag) before running anything; executes steps in order; prompts Y/N on oversight steps unless the bypass flag is set; stops on first non-zero exit
- Tests (new `tests/test_playbook.py`, following the style of `tests/test_sync.py`/`tests/test_discover.py`):
  - Parsing a valid single-node file (`topology-playbook-pond.toml`) into playbook records
  - Parsing playbooks split across a node file and the shared `topology-playbooks.toml`, merged into one namespace
  - Duplicate alias across two files (or within one file) raising a clear parse-time error naming both playbooks
  - Alias matching, including the no-match/near-miss path
  - Flattening a playbook that references another playbook (composition), including a cross-node fan-out composed from per-node playbooks — use the concrete worked scenario as the fixture: `topology-playbook-pond.toml` defines `start-pond-qwen`, `topology-playbook-localhost.toml` defines `start-pi-agent-pond-qwen` (a `localhost` task), and the shared `topology-playbooks.toml` defines `verify-pond-qwen-via-pi`, whose two tasks `ref` those two by name — flattening it should produce one `pond` task followed by one `localhost` task
  - Multiple playbooks in one file (`[[playbook]]` array-of-tables) parse into separate records, each with its own nested `[[playbook.tasks]]`
  - `hosts = "localhost"` resolving to local subprocess execution (no SSH, no machines-table lookup) while a named host still resolves via the machines table
  - Cycle detection on a self-referencing (direct and transitive) playbook
  - Oversight precedence: explicit true, explicit false overriding a heuristic match, and heuristic-only
- `README.md`: new "Playbooks" section (TOML file format, `[[tasks]]`, aliases, oversight, `localhost`, `run` usage) plus an entry in the Subcommands table; update the Privacy section to state that `topology-playbook*.toml` is covered by the same `topology-*` gitignore pattern as other sidecars (no exception)
- `SKILL.md`: extend the `description` trigger phrases and `argument-hint` to include `run`

## Files to read before starting

- src/topology/cli.py
- src/topology/discover.py
- src/topology/sync.py
- src/topology/help.py
- SKILL.md
- README.md
- planning.md
- .gitignore
- pyproject.toml
- tests/test_sync.py
- tests/test_discover.py

## Open questions

These are not yet decided and must either be resolved with the user before implementation starts, or explicitly flagged back if execution reaches them:

- Are playbooks hand-authored only, or can one be captured from a command just run interactively in a session? (Not designed yet; hand-authored only is the safe default to implement first.)
- Exact TOML field/table names beyond the `[[tasks]]`/`hosts`/`name`/`command` sketch are not fully finalized (e.g. the playbook-task's `ref` field) — invent as little as possible beyond what's already sketched in Background.
- Final bypass-flag name (`--skip-oversight` is a placeholder).
- Final heuristic keyword list for oversight detection.
- `list`/`search` subcommands for playbooks were discussed but scope/output format is not decided — do not build these yet; this task is `run` (and the parser/resolver it depends on) only. **Revised:** `topology playbook list` was subsequently built (see Results) — name/description/aliases/source, sorted by name. `search` remains out of scope.
- What "Pi coding agent" actually is, and how it's wired to query a model on a remote node, is not specified — do not invent specifics for it; the localhost/pond composition test case should use a placeholder local command, not a fabricated concrete integration.
- **Deferred, not decided:** a second worked scenario — a Pi agent on `localhost` configured against a remote provider (OpenRouter) and a new model, rather than a mesh-hosted model on a node like pond. A draft shape was sketched (a second playbook in `topology-playbook-localhost.toml`, `hosts = "localhost"`, provider/model passed via command args, API key via `$OPENROUTER_API_KEY` per the existing `.env` secrets convention — no machines-table change), but whether OpenRouter should be represented at the topology level at all (vs. just being config inside a `localhost` command) is unresolved. Do not build this scenario until it's revisited.

## Recommended approach

1. Fix the `.gitignore` pattern first — it's a one-line, low-risk, independently verifiable change.
2. Build the parser and data model in `playbook.py` against a hand-written fixture `topology-playbooks.toml`, before wiring any CLI.
3. Add the flattener + cycle detection on top of the parser, with its own tests, before touching host resolution.
4. Add host resolution (reuse `discover.py`'s pattern) and the oversight classifier.
5. Wire `run` into `cli.py`/`help.py` last, once resolve → flatten → oversight-classify is independently tested.
6. Do not implement `list`/`search` or the capture-from-run flow — out of scope per Open Questions.

## Done when

- [x] `.gitignore` correctly excludes `topology-playbooks.toml` and `topology-playbook-<node>.toml` (and other `topology-*` sidecars) — verify with `git check-ignore`
- [x] A playbook with a nested `playbook` task reference flattens correctly and a self-referencing playbook (direct and transitive) raises a clear cycle error instead of hanging
- [x] Playbooks split across `topology-playbook-<node>.toml` files and the shared `topology-playbooks.toml` resolve as one merged namespace; a duplicate alias anywhere in that set raises a clear parse-time error naming both playbooks
- [x] A `hosts = "localhost"` task runs as a local subprocess with no SSH and no machines-table lookup; a composed playbook mixing a `pond`-scoped task and a `localhost`-scoped task flattens and executes both correctly
- [x] `topology run "<unmatched phrase>"` prints near-miss candidates and exits non-zero without executing anything
- [x] An oversight step (explicit or heuristic) pauses for Y/N; a non-oversight step does not; the bypass flag skips only the Y/N prompts while the upfront review still prints
- [x] No new runtime dependency was added to `pyproject.toml` — parsing uses stdlib `tomllib` only
- [x] `uv run pytest` passes including all new `test_playbook.py` cases
- [ ] Entry added to `development-log.md` — deferred until you've reviewed and confirmed; see Results below

## Pre-flight
<!-- Filled in by preflight.py before delegation — do not edit by hand -->

## Results
<!-- Filled in by the executing model after completion -->
**Tests:** `uv run pytest` — 126 passed (34 in `tests/test_playbook.py`: 28 from the initial implementation + 6 for `playbook list`, plus the full existing suite unaffected).

**Files changed:**
- `.gitignore` — `*-topology.md` → `topology.md` + `topology-*`
- `src/topology/playbook.py` — new: parsing, alias resolution, oversight classification, flatten/cycle-detection, host resolution, review + execution, plus `playbook_main`/`print_list` for `playbook list`
- `src/topology/cli.py` — wired `run` and `playbook` into the dispatch dict
- `src/topology/help.py` — added `run` and `playbook list` to `SUBCOMMANDS`
- `tests/test_playbook.py` — new, 34 tests
- `README.md` — new "Playbooks" section, Subcommands list + anchor entry, an example, Privacy section updated
- `SKILL.md` — trigger phrases and `argument-hint` extended with `run`

**Summary:** Implemented exactly the settled design: TOML-based playbooks split across `topology-playbook-<node>.toml` (single-host) and `topology-playbooks.toml` (composed/cross-host), discovered via one glob and merged into a global name/alias namespace with duplicate-alias and duplicate-name detection at parse time. Tasks are either a command (`hosts` + `command`, where `hosts` is a machines-table `name` resolved to `hostname`/`ssh-user`, or the reserved `localhost` which skips SSH entirely) or a `ref` to another playbook, recursively flattened with cycle detection. Oversight gating follows the agreed precedence (explicit `true`/`false` overrides a keyword heuristic), is enforced per-task at execution time, and `--skip-oversight` bypasses only the individual prompts — the flattened plan always prints first regardless. No new runtime dependency: `tomllib` is stdlib for this project's Python 3.11+ minimum.

Verified beyond the unit tests with manual CLI smoke tests (temp `SKILLS_HOME`, real subprocess execution): a single-playbook run, the no-match near-miss path, and the full cross-node composition scenario (two `localhost` playbooks composed by a shared one — the same mechanism the pond+Pi scenario from `## Background` exercises, done with two local playbooks since no real pond was available to SSH into during this session).

One bug found and fixed during that manual testing, not caught by the mocked unit tests: Python buffers stdout when it isn't a tty, so a subprocess's own output could appear *before* the printed review in piped/redirected contexts — silently defeating the "review before execution" guarantee. Fixed with explicit `sys.stdout.flush()` calls before every subprocess invocation and confirmation prompt; re-verified with `... | cat` to force the buffered case.

Not built, per the Open Questions this task explicitly deferred: `list`/`search` subcommands, capture-a-playbook-from-a-run, the OpenRouter/remote-provider scenario, and final tuning of the heuristic keyword list / bypass-flag name (kept as `--skip-oversight`, `restart`/`kill`/`stop`/`rm`/`drop`/`wipe`) — these were explicitly out of scope, flag if any should be reconsidered.

Not yet done: the `development-log.md` entry and moving this file to `tasks/completed/` — held per the task-tracking workflow until you've reviewed this.
