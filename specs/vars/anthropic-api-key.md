---
id: VAR-ANTHROPIC-API-KEY
title: Anthropic API Key
status: draft
owners: [pipeline-team]
---

# VAR-ANTHROPIC-API-KEY

- **required:** no
- **type:** secret-ref
- **sensitivity:** secret
- **description:** Credential used by `llm-endpoint` (D18) to call
  Anthropic's API on behalf of every caller that needs a model call
  (`generator`, `test-author`, `spec-completeness-assistant`,
  `merge-orchestrator`'s `judge` wiring) — none of which hold this
  credential themselves. No example or default — forbidden for any
  `sensitivity: secret` var.

  **Resolution mechanism (`D32`):** a direct process-environment lookup
  of the OS environment variable named exactly `ANTHROPIC_API_KEY` — the
  same variable name the Anthropic SDK itself already reads by default
  when no key is passed explicitly, so this is the credential already
  present in any environment that has `claude`/the SDK configured at
  all, not a second, separately-provisioned secret. `llm-endpoint`
  (`R-ENDPOINT-003`) MUST read it this way — a plain environment lookup,
  never a vault/secrets-manager indirection — v1's one backend needs no
  more than that, and inventing one would be exactly the premature
  abstraction `D4`/`D6` already reject elsewhere in this corpus.

  **This is a real environment fact a caller MUST confirm for
  themselves, not something this spec can declare true on their
  behalf:** if `ANTHROPIC_API_KEY` is set, Anthropic's own tooling
  (including the `claude` CLI) treats it as authoritative and bills
  through it, unconditionally outranking any separate claude.ai/Pro-plan
  login in the same environment — confirmed by hand, not assumed. A
  project wanting `llm-endpoint` calls billed against a Pro/Max plan
  instead sets this variable unset in whatever environment actually
  invokes it, and `llm-endpoint` dispatches against that plan's login
  instead (`R-ENDPOINT-003`, `D82`) — no longer a hard requirement with
  no fallback, since `D82` added one.
