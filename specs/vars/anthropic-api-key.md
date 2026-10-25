---
id: VAR-ANTHROPIC-API-KEY
title: Anthropic API Key
status: draft
owners: [pipeline-team]
---

# VAR-ANTHROPIC-API-KEY

- **required:** yes
- **type:** secret-ref
- **sensitivity:** secret
- **description:** Credential used by `llm-endpoint` (D30) to call
  Anthropic's API on behalf of every caller that needs a model call
  (`generator`, `test-author`, `spec-completeness-assistant`,
  `merge-orchestrator`'s `judge` wiring) — none of which hold this
  credential themselves. No example or default — forbidden for
  `sensitivity: secret` (D12).
