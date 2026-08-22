---
name: topology
description: Read the local system topology to discover available machines and models. Triggers on "topology", "what models are available", "which machines are running", "start a model", "show me the topology", "sync topology", "refresh topology", "benchmark llm", "benchmark model", "test llm", "run benchmark", "help", "show help", "list subcommands".
argument-hint: "[sync | benchmark <hostname> <model> | show | help]"
---

Reads `$TOPOLOGY_PATH` (default `$SKILLS_HOME/topology.md`) to enumerate machines and models. On first run, if no topology file exists, guides the user through setup automatically.
