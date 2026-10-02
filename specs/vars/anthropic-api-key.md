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
- **description:** Credential used by `generator` and
  `cross-model-divergence-checker` to call the canonical model vendor's API.
  No example or default — forbidden for `sensitivity: secret` (D12).
