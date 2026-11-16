# R-PROVCHECK-008

**R-PROVCHECK-008** — `check_sealed_provenance(component_id, repo_root)`
  MUST return a `SealedCheckResult` (`interface/data/SealedCheckResult.md`)
  whose `reason` is the first of these that applies, and `null` if none:

  1. `not_sealed` — `current_sealed_key` returns `None`;
  2. `manifest_missing` — `<repo_root>/<source_path>/.sealed-provenance.json`
     does not exist;
  3. `manifest_invalid` — it is unreadable or is not a valid manifest
     under `interface/data/SealedProvenance.md`;
  4. `component_mismatch` — its `component_id` or `source_path` differs
     from the component's;
  5. `source_changed` — its `source_hash` differs from the key's;
  6. `owners_changed` — its `owners` list differs from the key's;
  7. `verifier_changed` — its `verifier_version` differs from the key's;
  8. `characterization_failed` — its `characterization.overall` is not
     `"pass"`.

  On any `reason` but `null`, `verification_report`, `owners`,
  `source_hash`, and `written_at` are `null`.

  A manifest is evidence only as a whole: nothing is taken from one that
  is not valid, and every difference above makes it stale rather than
  partly trusted. MUST be read-only (`R-PROVCHECK-004`).
