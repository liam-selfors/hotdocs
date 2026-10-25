---
id: P-AMBIGUITY-GATE
title: Ambiguity Is Caught Before Merge
status: draft
owners: [pipeline-team]
---

# Ambiguity Is Caught Before Merge

## Purpose

An underspecified acceptance criterion — one that an independent,
competent reading can satisfy in a way the spec author didn't intend — is
a spec defect, and the pipeline blocks the merge on it rather than letting
it reach `main` silently.

## Scope

In scope, for this build: structural ambiguity, caught by `spec-linter`'s
mechanical checks (missing traceability, malformed criteria, dangling
references) — the one detection mechanism currently active.

Out of scope, both deliberately: behavioral ambiguity that only a second,
independently-generated build comparison could surface, and judgment
ambiguity that only two independent `llm-judge` evaluations disagreeing
could surface. This build runs a single model and **exactly one judge call
per `llm-judge`-kind criterion per verification run** (`R-VERIFY-003`) —
simplified, not a capability gap: a disagreement-detecting judge mechanism
was never built, and building it now was deferred in favor of the single-
call design actually in place. Both deferred designs (cross-model
divergence, dual-judge disagreement) are recorded in
`notes/initial-ideas.md`'s Future Enhancements section (§14), not lost —
accepted as a tracked, visible tradeoff, not a gap this capability claims
to close.

## Golden scenarios

### GS-AMBIGUITY-001
Covers: P-AMBIGUITY-GATE
Kind: generated-test

```gherkin
Given a component spec whose Behavior section contains a requirement with no
  covering acceptance criterion
When the spec change is submitted to the pipeline
Then spec-linter reports a fail-severity finding and the merge is blocked
  before generation runs
```

