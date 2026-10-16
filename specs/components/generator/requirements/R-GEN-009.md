# R-GEN-009

**R-GEN-009** — Writing output MUST be confined to `gen/<component>/` for
  the target component only. It MUST NOT write to any `sealed` component's
  `source_path`, and MUST NOT overwrite a file listed in that component's
  `gen/<component>/.overrides.json` (the two declared cold-regen exemptions,
  §9) — generation must never silently clobber a declared hands-off path.
