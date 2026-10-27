# `VerifyReport`

```json
{
  "scope": "blast-radius",
  "ready": false,
  "components": {
    "comp-foo": { "...": "a ComponentPipelineResult" }
  },
  "capabilities": {
    "P-ZERO-EDIT": { "...": "a CapabilityProvenanceCheckResult" }
  },
  "not_ready_reasons": ["comp-foo: no provenance for current spec state — run hotdocs build comp-foo"]
}
```

`scope` is `"blast-radius"` when `check_readiness` was called with
`changed_ids`, `"whole-corpus"` otherwise (`R-TRACK-009`). `components`
and `capabilities` are keyed by id, each value copied verbatim from
`component-gate-runner`'s `run_component_gates` result or
`capability-scenario-verifier`'s `run_capability_gates` result
(`CapabilityProvenanceCheckResult`) respectively — never recomputed or
summarized by this component, and never a fresh call to
`provenance-checker` itself (`run_component_gates` already made that
check, or skipped it on a hit). `ready` (`R-TRACK-010`) is `true` only
if every entry in both maps is passing. `not_ready_reasons` names every
failing or missing entry, human-readable — what `hotdocs build`'s exit
code alone can't convey.
