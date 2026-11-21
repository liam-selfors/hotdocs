# R-GATE-008

**R-GATE-008** — On every non-sealed miss, the `on_attempt` callback MUST
  call `provenance-tracker`'s `write_attempt_record` once per attempt,
  passing that attempt's `GenerationResult`, its `VerificationReport` or
  `None`, and the provenance key's `spec_bundle_hash`. An exception from
  that call MUST NOT change this component's result. `attempts` in
  `ProvenanceInputs` is the number of files in
  `<repo_root>/.hotdocs/attempts/<component_id>/` after the loop, the
  directory `write_attempt_record` writes to.
