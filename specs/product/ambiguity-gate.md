---
id: P-AMBIGUITY-GATE
title: Ambiguity Is Caught Before Merge
status: draft
owners: [pipeline-team]
---

# Ambiguity Is Caught Before Merge

## Purpose

An underspecified acceptance criterion — one that two independent, competent
readings (a lint rule, a second model's build, two `llm-judge` evaluators)
can satisfy in behaviorally different ways — is a spec defect, and the
pipeline blocks the merge on it rather than letting it reach `main` silently.

## Scope

In scope: structural ambiguity (caught by `spec-linter`), behavioral ambiguity
(caught by the D3 cross-model divergence check when enabled), and judgment
ambiguity (caught by D5's `llm-judge` disagreement check when enabled). Out of
scope: ambiguity in components running single-model mode with both D10
toggles off — accepted as a tracked, visible tradeoff (D10), not a gap this
capability claims to close.

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

### GS-AMBIGUITY-002
Covers: P-AMBIGUITY-GATE
Kind: generated-test

```gherkin
Given a component with cross_model_divergence_check enabled and a second
  model configured, and an acceptance criterion loose enough that two models
  can both pass verification with behaviorally different implementations
When the pipeline runs the cross-model divergence check
Then the merge is blocked as a spec defect, not a code defect, and the
  blocking reason names the under-constrained criterion
```
