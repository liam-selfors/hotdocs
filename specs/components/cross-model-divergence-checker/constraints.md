---
id: comp-cross-model-divergence-checker-constraints
title: Cross-Model Divergence Checker — Non-Functional Constraints
status: draft
owners: [pipeline-team]
---

# Cross-Model Divergence Checker — Non-Functional Constraints

- **This component's own logic is deterministic; what it calls isn't.**
  Given the same two candidates and the same test inputs, the comparison
  (R-XMODEL-004) MUST always produce the same `diverged` result. This says
  nothing about whether calling `generator` twice with the same second
  model produces the same candidate both times — it generally won't, which
  is exactly why the comparison has to run fresh each time, not be cached
  across different `generator` calls the way `cache-manager`'s keys assume
  for a single candidate.
- **Isolation.** The second candidate MUST NOT be written anywhere that
  could be mistaken for, or accidentally promoted ahead of, the canonical
  `gen/<component>/` tree except through D10's explicit, recorded promotion
  path.
- **Cost awareness.** `standby-only` mode (R-XMODEL-007) MUST NOT perform
  the comparison step at all — not run it and discard the result, actually
  skip it — since the whole point of that mode is buying the availability
  benefit without paying the comparison's cost.
