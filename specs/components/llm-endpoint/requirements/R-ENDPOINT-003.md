# R-ENDPOINT-003

**R-ENDPOINT-003** — v1 MUST implement exactly one backend (Anthropic,
  via `VAR-ANTHROPIC-API-KEY` when configured, resolved by a plain
  process-environment lookup — see that var's own spec for the
  resolution mechanism and its Pro-plan-vs-API-billing precedence
  caveat, `D32`) — no OpenAI/open-model backend, and no
  backend-plugin/registry machinery, built in now for vendors nothing in
  this corpus actually calls yet (same anti-premature-abstraction
  reasoning `D4` applied to `criterion-compiler`'s single emit target).
  A future backend MUST be addable as a new implementation behind
  `R-ENDPOINT-002`'s existing resolve/dispatch split, never a redesign of
  the public `complete()` contract (`R-ENDPOINT-001`) or of any caller.

  **When this backend dispatches via the `claude` CLI's non-interactive
  mode (`D33`), it MUST invoke it with `--tools ""`, every call,
  unconditionally** (`D35`) — found necessary by a real failure, not
  assumed: without it, the CLI retains its normal tool access
  (`Read`/`Bash`/etc.) even with a `system_prompt` instructing otherwise,
  which only asks the model not to explore rather than structurally
  preventing it from being able to — a real `R-GEN-001` cold-mode purity
  violation caught live, where a call without this flag used tool access
  to inspect this actual repository's current git state instead of
  treating the prompt as an isolated completion. This is a structural
  guarantee, the same posture `R-ENDPOINT-005` already takes for
  credential handling — not merely a documented convention a system
  prompt is trusted to uphold on its own.

  **It MUST additionally pass `--bare` when `VAR-ANTHROPIC-API-KEY` is
  configured, or `--safe-mode` when it is not** (`D82`) — both
  structurally suppress CLAUDE.md/hooks/plugin auto-discovery, the other
  half of the same cold-mode purity guarantee, but `--bare` additionally
  and unconditionally refuses any non-API-key credential (confirmed by
  the `claude` CLI's own documented behavior), which would make a call
  impossible for a caller billing against a Pro/Max subscription login
  instead of an API key. This component MUST NOT pre-empt the call by
  checking for the credential itself and refusing early — it dispatches
  either way and classifies whatever the CLI itself reports (`R-ENDPOINT-004`).
