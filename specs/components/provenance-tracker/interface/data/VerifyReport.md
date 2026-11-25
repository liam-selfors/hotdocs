# `VerifyReport`

```json
{
  "scope": "blast-radius",
  "ready": false,
  "components": {
    "comp-foo": { "...": "a ProvenanceCheckResult" }
  },
  "capabilities": {
    "P-ZERO-EDIT": { "...": "a CapabilityProvenanceCheckResult" }
  },
  "secret_scan": { "...": "a SecretScanResult, or null" },
  "not_ready_reasons": ["comp-foo: no provenance for current spec state — run hotdocs generate comp-foo"]
}
```

`scope` is `"blast-radius"` when `check_readiness` was called with
`changed_ids`, `"whole-corpus"` otherwise (`R-TRACK-009`). `components`
and `capabilities` are keyed by id, each value copied verbatim from
`provenance-checker`'s `ProvenanceCheckResult` or
`capability-scenario-verifier`'s `run_capability_gates` result
(`CapabilityProvenanceCheckResult`) respectively — never recomputed or
summarized by this component. `secret_scan` is the one fresh
repository scan (`R-TRACK-016`), never a component's stored one. `ready` (`R-TRACK-010`) is `true` only if
every entry in both maps is a hit with a passing result and the
secret scan, when one was due, ran and is not flagged. `not_ready_reasons`
names every failing or missing entry, human-readable — what `hotdocs
verify`'s exit code alone can't convey.
