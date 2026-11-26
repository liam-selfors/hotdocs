# R-PROVCHECK-011

**R-PROVCHECK-011** — A miss on `spec_bundle_hash` MUST instead have
  `reason` `dependency code differs` (`D379`) exactly when
  `spec_bundle_parts` is given, the manifest's `spec_bundle_parts` is an
  object whose `spec` equals the given `spec` and whose
  `dependency_code` differs, and the check would otherwise hit: every
  `gate_versions` entry and the assets and drivers values match (`R-PROVCHECK-001`,
  `R-PROVCHECK-009`). A manifest with no `spec_bundle_parts`, or any
  other difference, keeps the reason it would have had without them.
