# R-AUTHOR-003

**R-AUTHOR-003** — Model selection MUST use the canonical model alone —
  the single-model-must-keep-working posture D10 established, applied here
  (same degraded behavior that would apply "when no second model is
  configured," now the only behavior this requirement specifies).

  **Deferred, not dropped:** a second-model preference for authoring —
  selecting a model different from the one `generator` used for that
  component's current code, when one is configured, to make "independent
  path" true in practice and not just in name — was the original design
  here, cut alongside the broader second-model scope reduction for this
  build (see `cross-model-divergence-checker/component.md`'s build-status
  note and `notes/initial-ideas.md` §10). Authoring with the same model as
  the code under test is weaker evidence than a genuinely independent
  model would provide, but still produces a real, executable test — this
  requirement does not claim stronger independence than single-model
  authoring actually has. Reintroducing the preference, if second-model
  support returns, is additive: a new conditional branch on top of this
  one, not a rewrite of it.
