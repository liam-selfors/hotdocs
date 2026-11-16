---
id: VAR-HOTDOCS-CONFIG
title: Hotdocs Config Path
status: draft
owners: [pipeline-team]
---

# VAR-HOTDOCS-CONFIG

- **required:** no
- **type:** path
- **sensitivity:** non-secret
- **description:** Where `llm-endpoint` reads the `hotdocs.toml` that
  chooses its provider (`R-ENDPOINT-007`), read from the environment
  variable `VAR_HOTDOCS_CONFIG` (glossary: "Var environment name"). Absent
  means `hotdocs.toml` in the current directory, and without that a bare
  `claude-*` model name uses the `claude` command. A path naming a file
  that does not exist is an error, never silently ignored. The file holds
  no secret: it names the environment variable that does.
- **example:** `config/hotdocs.toml`
