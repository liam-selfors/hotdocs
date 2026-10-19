# R-GEN-001

**R-GEN-001** — Given a `SpecBundle` in `cold` mode, the model call MUST
  be constructed from exactly the bundle's `spec` / `interface` /
  `constraints` / `dependency_interfaces` / `vars` / `glossary` fields —
  never `hint_code` (which is `null` in cold mode anyway, per
  `spec-bundle-assembler` R-ASSEMBLE-008) and never the component's current
  `gen/<component>/` content from any other source.

  `retry_feedback` (R-GEN-010) is **not** an exception to this rule and
  does not weaken it — it carries no code, prior or otherwise, only
  `R-id`-level pass/fail derived entirely from the current spec bundle's
  own requirements and the current attempt sequence's own output. A `cold`
  call that includes `retry_feedback` is still, by this requirement's own
  test, constructed from nothing but the current spec bundle (plus a
  derived fact about it) — never from external or stale state the way
  `hint_code` is.
