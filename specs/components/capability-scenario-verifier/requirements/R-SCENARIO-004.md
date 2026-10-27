# R-SCENARIO-004

**R-SCENARIO-004** — MUST expose `check_capability_provenance(capability_id,
  repo_root) -> CapabilityProvenanceCheckResult` and
  `run_capability_gates(capability_id, repo_root, judge=None,
  test_author=None) -> CapabilityProvenanceCheckResult` (`D89`).

  **The provenance key is a hash of every realizing component's actual
  current `gen/` content** (found via `R-SCENARIO-002`'s existing
  capability-intersection lookup, inverted to "every component whose
  `realizes` includes this `P-id`") — deliberately **not** a hash of
  their `spec_bundle_hash`es. A `spec_bundle_hash`-keyed check would
  reopen the exact blind spot this component exists to close (`D2`): a
  parent changing something undeclared and invisible to spec-level
  hashing that a dependent silently relies on. Hashing actual content
  invalidates on *any* real change anywhere in the realizing set,
  whether or not blast-radius analysis or a declared
  `depends_on_guarantees` edge would have flagged it.

  `check_capability_provenance` reads the committed record at
  `verification/capabilities/<capability_id>/.provenance.json` (if any)
  and compares its recorded hash against the current one — a hit if
  they match. `run_capability_gates` checks first; on a hit, returns it
  unchanged (no scenarios re-run); on a miss, runs that capability's
  scenarios (`R-SCENARIO-001`, scoped to just this one `P-id`'s
  realizing components) and writes a fresh record before returning the
  result.
