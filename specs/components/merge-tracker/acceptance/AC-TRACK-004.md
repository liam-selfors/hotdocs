# AC-TRACK-004

Covers: R-TRACK-004
Kind: generated-test

```gherkin
Given merge-orchestrator calling write_tracking_record with component_ids,
  block_reasons, overall, and changed_ids as plain parameters, and
  provenance-writer's manifests already present on disk for each
  component id
When write_tracking_record runs
Then it reads per-component detail only from the on-disk provenance
  manifests, never from a parameter typed as merge-orchestrator's
  MergeResult — confirmed by this component's own depends_on listing only
  comp-provenance-writer, not comp-merge-orchestrator
```
