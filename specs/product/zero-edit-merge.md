---
id: P-ZERO-EDIT
title: Zero-Human-Edit Merge
status: draft
owners: [pipeline-team]
---

# Zero-Human-Edit Merge

## Purpose

The headline claim of the whole methodology (`notes/initial-ideas.md` §10):
a ratified spec change produces correct, deployable code via the pipeline
alone — no human ever hand-edits `gen/` to make a merge pass.

## Scope

In scope: component spec changes that pass lint and have complete acceptance
criteria. Out of scope: `sealed` components and `.overrides.json`-pinned
files, which are explicitly exempt from this capability's promise (D1/§9).

## Golden scenario

### GS-ZERO-EDIT-001
Covers: P-ZERO-EDIT
Kind: generated-test

```gherkin
Given a ratified, non-sealed component spec bundle with complete,
  agent-checkable acceptance criteria
When a spec change is merged through the pipeline (lint → generation →
  verification → review packet → merge)
Then the resulting gen/<component>/ passes every gate with zero commits to
  gen/<component>/ authored by a human between the spec merge and the
  pipeline's own merge commit
```
