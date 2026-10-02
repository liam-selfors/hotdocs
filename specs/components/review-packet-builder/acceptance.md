---
id: comp-review-packet-builder-acceptance
title: Review Packet Builder — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Review Packet Builder — Acceptance Criteria

All ten criteria are `kind: compiled` — formatting already-computed results
is pure, deterministic logic. An eighth component in this corpus whose
entire acceptance set is `compiled`.

### AC-PACKET-001
Covers: R-PACKET-001
Kind: compiled

```gherkin
Given a PR changing one component's spec.md
When build_review_packet runs
Then spec_diff contains the actual diff text for that file
```

### AC-PACKET-002
Covers: R-PACKET-002
Kind: compiled

```gherkin
Given a PR adding one new requirement R-FOO-002
When build_review_packet runs
Then changed_requirements includes R-FOO-002
```

### AC-PACKET-003
Covers: R-PACKET-003
Kind: compiled

```gherkin
Given a blast radius of two components from impact-analyzer
When build_review_packet runs
Then regenerated_components lists exactly those two component ids
```

### AC-PACKET-004
Covers: R-PACKET-004
Kind: compiled

```gherkin
Given a VerificationReport with one passing and one failing criterion
When build_review_packet runs
Then verification_results shows both results individually, not only an
  aggregate pass/fail
```

### AC-PACKET-005
Covers: R-PACKET-005
Kind: compiled

```gherkin
Given clean license-scan and secret-scan results
When build_review_packet runs
Then compliance_flags is present with both fields explicitly empty, not
  omitted
```

### AC-PACKET-006
Covers: R-PACKET-006
Kind: compiled

```gherkin
Given one component was a cache hit and another was not
When build_review_packet runs
Then cache_hit_status reflects both accurately, per component
```

### AC-PACKET-007
Covers: R-PACKET-007
Kind: compiled

```gherkin
Given a PR that newly marks a component sealed: true
When build_review_packet runs
Then exemption_changes.sealed includes that component
```

### AC-PACKET-008
Covers: R-PACKET-008
Kind: compiled

```gherkin
Given a second-model verification failure that did not block the merge
When build_review_packet runs
Then residual_risk includes that finding
```

### AC-PACKET-009
Covers: R-PACKET-009
Kind: compiled

```gherkin
Given a merge with zero flags, zero warnings, and full cache hits
When build_review_packet runs
Then a packet is still produced, not skipped
```

### AC-PACKET-010
Covers: R-PACKET-010
Kind: compiled

```gherkin
Given a component whose generated code changed substantially
When build_review_packet runs
Then the packet contains no generated-code diff content anywhere in it
```
