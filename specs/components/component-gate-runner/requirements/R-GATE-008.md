# R-GATE-008

**R-GATE-008** — On every non-sealed miss, MUST call
  `provenance-tracker`'s `write_attempt_record` (`R-TRACK-004`, `D19`)
  once, after generation, any verification, and both scans conclude,
  passing the full `GenerationResult`, the full `VerificationReport` or
  `None` when verification was never reached, and the provenance key's
  `spec_bundle_hash`. Called for every outcome — a failed attempt's
  detail is what a developer needs to choose `--retry-feedback` next
  time. An exception from this call MUST NOT change this component's
  result.
