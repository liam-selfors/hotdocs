---
id: P-MERGE-VISIBILITY
title: Merge Status Is Visible and Recoverable
status: draft
owners: [pipeline-team]
---

# Merge Status Is Visible and Recoverable

## Purpose

A merge touching several components, where some succeed and some fail, is
not a black box. A developer can see, per component, what happened on the
most recent attempt — without re-reading CLI output they may not have
kept — and correcting the failing component(s) and re-running the merge
recovers the succeeding ones for free, at no repeated cost.

## Scope

In scope: durable, queryable visibility into every merge attempt (success
or block) for the local developer who ran it. Out of scope: a dedicated
"resume" or "retry" feature (`R-MERGE-018` already makes re-running the
merge itself the complete recovery path — this capability is about
*seeing* that clearly, not a separate mechanism); sharing this visibility
across developers or machines (a deferred, not-yet-speced future
enhancement, `notes/initial-ideas.md` §14).

## Capability scenario

### CS-MERGE-VISIBILITY-001
Covers: P-MERGE-VISIBILITY
Kind: generated-test

```gherkin
Given a merge attempt touching three components where two succeed and one
  exhausts its retries, followed by a spec edit to the failing component
  and a second merge attempt
When a developer queries the local tracking store after each attempt
Then the first query shows all three components' outcomes from the first
  attempt, and the second query shows the two unchanged components' prior
  (still cache-hit) outcomes alongside the third component's fresh result
  — without needing to have kept the first attempt's CLI output
```
