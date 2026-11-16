# R-AUTHOR-007

**R-AUTHOR-007** — A model-call error MUST be reported as a distinct
  failure mode from "the authored test ran but failed" — mirrors R-GEN-008's
  classification distinction, consumed by `verifier-orchestrator` to tell
  "could not author a test" apart from "the test says the criterion isn't
  met."
