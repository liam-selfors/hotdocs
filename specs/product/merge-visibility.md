---
id: P-MERGE-VISIBILITY
title: Merge Status Is Visible and Recoverable
status: draft
owners: [pipeline-team]
---

# Merge Status Is Visible and Recoverable

## Purpose

When a change touches several components and some are ready while others
are not, that is not a black box. A developer can see, per component,
whether it is ready and why not — without re-reading CLI output they may
not have kept — and fixing the failing component's spec and regenerating
it leaves the ready ones ready, at no repeated cost.

## Scope

In scope: a durable, queryable answer to "is each component ready" for
the local developer, as `provenance-tracker` computes it live from each
component's provenance. Out of scope: a "resume" or "retry" feature
(re-running `hotdocs generate` on the failing component is the complete
recovery path; this capability is about *seeing* that clearly); sharing
this view across developers or machines (`notes/initial-ideas.md` §14).

## Capability scenario

### CS-MERGE-VISIBILITY-001
Covers: P-MERGE-VISIBILITY
Kind: generated-test

```gherkin
Given a corpus that passes `hotdocs lint` at every step, and
  a change touching three components where two generate and verify
  and one fails verification, followed by a spec edit to the failing
  component and a second `hotdocs generate` of it
When a developer queries provenance-tracker after each step
Then the first query shows two components ready and one not ready with its
  reason, and the second shows the two unchanged components still ready
  (provenance hits, not regenerated) alongside the third's fresh result —
  without needing the first run's CLI output
```
