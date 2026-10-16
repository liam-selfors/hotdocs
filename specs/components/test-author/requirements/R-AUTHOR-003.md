# R-AUTHOR-003

**R-AUTHOR-003** — Model selection MUST prefer a model different from the
  one `generator` used for that component's current code, when a second
  model is configured — this is what makes "independent path" true in
  practice, not just in name. When no second model is configured, this
  component MUST fall back to the canonical model alone (the same
  single-model-must-keep-working posture D10 established, applied here as
  a fourth instance — authoring with the same model as the code under test
  is weaker evidence, but still produces a real, executable test, which is
  strictly better than no test at all).
