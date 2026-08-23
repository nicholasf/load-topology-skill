# Exclude topology-backup* files from sidecar filter

**Created:** 2026-08-22 11:06:08
**Model:** qwen3.8-27b on pond via Ollama (ask-remote-llm bridge mode; agent runtimes are down) — small mechanical filter change, no cloud tokens needed
**Agent:** `n/a — executed via ask-remote-llm bridge (hermes/goose down per Agent State)`
**Status:** pending

## Goal

show.py prints topology.md plus the topology-*.md sidecar files it finds in SKILLS_HOME, but never picks up the topology-backup* files that sync.py writes.

## Background

sync.py backup() (scripts/sync.py line ~21) writes topology-backup.md into SKILLS_HOME before every sync. show.py collects sidecars with glob(os.path.join(skills_home, topology-*.md)) (line ~20), so the backup file is always included in output and counted in the (N sidecar file(s)) summary line, even though it is an artifact of this skill, not a file owned by a dependent skill.

## Changes

- In scripts/show.py, exclude any globbed file whose basename starts with topology-backup from the sidecar list, before printing and before counting
- Add a test (tests/test_show.py or extend an existing test module) that stages a tmp SKILLS_HOME containing topology.md, one real topology-*.md sidecar, and topology-backup.md, runs show main(), and asserts the sidecar is printed while the backup file is neither printed nor counted
- Update docs for consistency: command.md show-subcommand text (~line 192), command.md manual sidecar scan instruction (~line 64), README.md show section (~line 100), and README.md Sidecar files pattern block (~lines 307-311) should state that topology-backup* is a sync.py artifact and is excluded from the sidecar set

## Files to read before starting

- scripts/show.py
- scripts/sync.py
- command.md
- README.md
- tests/test_sync.py

## Recommended approach

Implement the exclusion in show.py first (filter the sorted glob results by basename prefix), then add the pytest test, then update the four doc locations. Keep the backup writing in sync.py untouched — it is intentional and documented.

## Done when

- [ ] With topology-backup.md present in SKILLS_HOME, show.py output contains no topology-backup section and the (N sidecar file(s)) count excludes it
- [ ] Real topology-*.md sidecars are still printed in sorted order
- [ ] uv run pytest passes including the new test

## Pre-flight ⏳⏳⏳ L3 (~260s) (local)

- Spec: 594 tokens
- Files: show.py (283), sync.py (1,717), command.md (2,328), README.md (3,804), test_sync.py (1,439) → 9,571 total
- Reasoning buffer: 12,000 (estimated)
- Estimated total: ~22,165 tokens
- Complexity: L3 — must split before sending
- Context window: 32,768 — OVERFLOW RISK
- Time estimate: ~260s at 85 t/s


## Results
<!-- Filled in by the executing model after completion -->
**Tests:**
**Files changed:**
**Summary:**
