---
id: P-DECISION-INTEGRITY
title: The Spec Corpus Stays Honest About Its Own Decision History
status: draft
owners: [pipeline-team]
---

# The Spec Corpus Stays Honest About Its Own Decision History

## Purpose

A decision record can be superseded by a later one, and a live spec
file citing the superseded decision can go stale — still reflecting a
conclusion the corpus itself has since reversed. The corpus can tell
a developer which citations are candidates for that, so staleness is
discoverable rather than silently accumulating (`D87`–`D89`).

## Scope

In scope: making decision supersession a real, queryable relationship
(`supersedes`/`status: deprecated`, mechanically validated); surfacing
candidate-stale citations for human review. Out of scope: fixing a
flagged file automatically, or blocking anything on a flagged result —
this capability is about visibility, the same posture
`P-MERGE-VISIBILITY` takes for merge attempts, never a second
ambiguity gate.

## Capability scenario

### CS-DECISION-INTEGRITY-001
Covers: P-DECISION-INTEGRITY
Kind: compiled

```gherkin
Given a decision record superseded by a later one, and a live spec
  file citing the superseded decision, last touched before the
  superseding decision was ratified
When decision-drift-detector runs
Then that file/citation pair appears in the drift report
```
