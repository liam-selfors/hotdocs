---
id: comp-spec-completeness-assistant-acceptance
title: Spec Completeness Assistant — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Spec Completeness Assistant — Acceptance Criteria

Mixed `kind`, and deliberately the opposite mix from most of this corpus:
R-ASSIST-001–003 and R-ASSIST-006 are `compiled` (dispatch, path/data
checks), but R-ASSIST-004/005 — this component's actual reason to exist —
are `llm-judge`. Unlike every coordination component specced so far
(`verifier-orchestrator`, `cross-model-divergence-checker`,
`merge-orchestrator`), this one's core value genuinely *is* judgment, not
dispatch around it — a useful contrast case for D5's guidance rather than
another confirmation of "prefer compiled."

### AC-ASSIST-001
Covers: R-ASSIST-001
Kind: compiled

```gherkin
Given a draft spec change with a hard-fail spec-linter finding
When assist runs
Then that finding is surfaced before any completeness or redundancy
  analysis is attempted
```

### AC-ASSIST-002
Covers: R-ASSIST-002
Kind: compiled

```gherkin
Given a draft change to one spec whose dependents impact-analyzer resolves
  to two components
When assist runs
Then predicted_blast_radius lists exactly those two components
```

### AC-ASSIST-003
Covers: R-ASSIST-003
Kind: compiled

```gherkin
Given a predicted blast radius of one component
When assist runs
Then hint_previews contains a hint-mode preview for that component,
  produced without a full cold regen
```

### AC-ASSIST-004
Covers: R-ASSIST-004
Kind: llm-judge

```gherkin
Given a draft change that adds a requirement with no acceptance criterion
  yet
When assist runs with a model configured
Then completeness_score reflects that gap and completeness_rationale names
  the specific missing criterion
```

### AC-ASSIST-005
Covers: R-ASSIST-005
Kind: llm-judge

```gherkin
Given a draft change that restates, in different words, a requirement
  already present elsewhere in the corpus
When assist runs with a model configured
Then redundancy_flags identifies the overlapping requirement
```

### AC-ASSIST-006
Covers: R-ASSIST-006
Kind: compiled

```gherkin
Given any CompletenessReport, however low its completeness_score
When merge-orchestrator's own dependency list and gating logic are
  inspected
Then neither references this component in any way that could block a merge
```

### AC-ASSIST-007
Covers: R-ASSIST-007
Kind: compiled

```gherkin
Given assist is called with no model configured
When it runs
Then lint_findings/predicted_blast_radius/hint_previews are still
  populated, degraded is true, and completeness_score/
  completeness_rationale/redundancy_flags are empty rather than guessed
```

### AC-ASSIST-008
Covers: R-ASSIST-008
Kind: compiled

```gherkin
Given a CompletenessReport with a non-trivial completeness_score
When the report's schema is inspected
Then it exposes fields a calling tool can use to record an accept/override
  decision, without this component itself persisting that decision anywhere
```
