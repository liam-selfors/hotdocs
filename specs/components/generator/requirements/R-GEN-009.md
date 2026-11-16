# R-GEN-009

**R-GEN-009** — Writing output MUST be confined to `gen/<component>/` for
  the target component only. It MUST NOT write to any `sealed` component's
  `source_path`, and MUST NOT overwrite a file listed in that component's
  `gen/<component>/.overrides.json` (the two declared cold-regen exemptions,
  §8) — generation must never silently clobber a declared hands-off path.

  This MUST be a **precondition check, resolved before any model call is
  attempted**, recorded as its own outcome (`refused`, see
  `interface/data/GenerationResult.md`), never a `model_call_error`.
  `check_write_allowed(bundle, repo_root)` performs exactly this check.
