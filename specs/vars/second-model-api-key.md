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
  `cross-model-divergence-checker` (D3), the D10 fallback-standby-build
  mechanism, and `test-author`'s second-model authoring preference. Its
  absence means the pipeline runs in single-model mode (D10) — this is a
  supported, accepted configuration, not a degraded error state. No
  example or default — forbidden for `sensitivity: secret` (D12).

  **Currently unreferenced by any component's `uses_var`**, not an error:
  every consumer above is deferred for this build (see
  `cross-model-divergence-checker/component.md`'s build-status note and
  `notes/initial-ideas.md` §10). Kept declared, not deleted, so the
  contract is ready to re-add to a consumer's `uses_var` without
  redesigning it.
