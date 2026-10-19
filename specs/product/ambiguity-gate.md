---
id: P-AMBIGUITY-GATE
title: Ambiguity Is Caught Before Merge
status: draft
owners: [pipeline-team]
---

# Ambiguity Is Caught Before Merge

## Purpose

An underspecified acceptance criterion — one that two independent, competent
readings (a lint rule, two `llm-judge` evaluators) can satisfy in
behaviorally different ways — is a spec defect, and the pipeline blocks the
merge on it rather than letting it reach `main` silently.

## Scope

In scope: structural ambiguity (caught by `spec-linter`), and judgment
ambiguity (caught by D5's `llm-judge` disagreement check when enabled). Out
of scope: behavioral ambiguity that only a second, independently-generated
build could surface — this build is single-model only (see
`notes/initial-ideas.md`'s Future Enhancements section for the deferred
cross-model divergence design) — accepted as a tracked, visible tradeoff,
not a gap this capability claims to close.

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

