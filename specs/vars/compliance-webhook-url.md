---
id: VAR-COMPLIANCE-WEBHOOK-URL
title: Compliance Webhook URL
status: draft
owners: [pipeline-team]
---

# VAR-COMPLIANCE-WEBHOOK-URL

- **required:** no
- **type:** url
- **sensitivity:** non-secret
- **description:** Endpoint `license-scanner` and `secret-scanner` notify when
  a flag crosses the severity threshold (`notes/initial-ideas.md`'s own
  D7/D12) — separate from, and in addition to, the merge-blocking outcome
  itself. Absent means no external notification is sent; flags are still
  written to the provenance manifest and review packet regardless.
- **example:** `https://hooks.internal/compliance/hotdocs`
