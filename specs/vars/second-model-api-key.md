---
id: VAR-SECOND-MODEL-API-KEY
title: Second Model API Key
status: draft
owners: [pipeline-team]
---

# VAR-SECOND-MODEL-API-KEY

- **required:** no
- **type:** secret-ref
- **sensitivity:** secret
- **description:** Credential for the optional second model used by
  `cross-model-divergence-checker` (D3) and the D10 fallback-standby-build
  mechanism. Its absence means the pipeline runs in single-model mode (D10) —
  this is a supported, accepted configuration, not a degraded error state. No
  example or default — forbidden for `sensitivity: secret` (D12).
