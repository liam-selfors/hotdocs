# R-GEN-009

**R-GEN-009** — Writing output MUST be confined to `gen/<component>/` for
  the target component only. It MUST NOT write to any `sealed` component's
  `source_path`, and MUST NOT overwrite a file listed in that component's
  `gen/<component>/.overrides.json` (the two declared cold-regen exemptions,
  §8) — generation must never silently clobber a declared hands-off path.

  This MUST be a **precondition check, resolved before any model call is
  attempted** — refusing only at write-time, after already paying for a
  model call whose output can never be used, wastes real cost for no
  benefit. The refusal MUST be recorded as its own distinct outcome
  (`refused`, see `interface/data/GenerationResult.md`) — neither a
  `model_call_error` (R-GEN-008, a real API failure) nor "produced code
  that fails verification"; conflating a precondition refusal with either
  of those would misclassify why nothing was generated.

  This is one of two independent enforcement layers (D5/§8): `merge-
  orchestrator` is expected not to call this component for a sealed
  component's regeneration at all (its own routing requirement), and this
  check is the second, independent layer — in case it's ever invoked
  anyway, by a bug or a future caller that doesn't yet know the routing
  rule.
