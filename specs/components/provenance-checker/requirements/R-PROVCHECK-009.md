# R-PROVCHECK-009

**R-PROVCHECK-009** — A component's current assets and drivers values
  MUST be the `assets` and `drivers` of `run-environment`'s
  `prepare(component_id, repo_root)`, whose `close()` is called at once
  (`D383`); a sealed component's (`R-PROVCHECK-007`) are `[]` and `[]`,
  with no call. `current_provenance_key` returns them as `assets` and
  `drivers`. `check_provenance` computes them itself, only once `gate_versions`
  match and either `spec_bundle_hash` matches or `R-PROVCHECK-011`'s
  parts test applies, and MUST miss when
  `prepare` reports `ok` false (reason its `failure_message`), when the
  manifest's `assets` differs (reason `assets differ`, or
  `R-PROVCHECK-010`'s `environment differs`), or when its `drivers`
  differs (reason `drivers differ`, or `environment differs`), checked
  in that order. A manifest with no `assets` field, or `null`, compares
  as `[]` and misses with `assets differ`; one with no `drivers` field,
  or `null`, compares as `[]`.
