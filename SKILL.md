---
name: load-topology
description: Read the local system topology to discover available machines and models. Triggers on "load topology", "what models are available", "which machines are running", "start a model", "show me the topology", "refresh topology", "benchmark llm", "benchmark model", "test llm", "run benchmark".
argument-hint: "[refresh | benchmark <hostname> <model>]"
---

Reads `$TOPOLOGY_PATH` (default `$SKILLS_HOME/topology.md`) to enumerate machines and models. Invoke `/load-topology` for the full workflow.
