---
id: comp-corpus-graph-builder-acceptance
title: Corpus Graph Builder — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Corpus Graph Builder — Acceptance Criteria

All eight criteria are `kind: compiled` — graph-walking and aggregation
over already-computed data. A ninth component in this corpus with a fully
`compiled` acceptance set.

### AC-GRAPH-001
Covers: R-GRAPH-001
Kind: compiled

```gherkin
Given a corpus with two product capabilities, three components, and one var
When build_corpus_graph runs
Then the graph contains exactly six nodes of the matching types
```

### AC-GRAPH-002
Covers: R-GRAPH-002
Kind: compiled

```gherkin
Given a component that depends_on another, realizes a capability, and uses
  one var
When build_corpus_graph runs
Then the graph contains all three corresponding edges
```

### AC-GRAPH-003
Covers: R-GRAPH-003
Kind: compiled

```gherkin
Given a component with a known VerificationReport and provenance manifest
When build_corpus_graph runs
Then that component's node carries both, plus its size status and sealed
  status
```

### AC-GRAPH-004
Covers: R-GRAPH-004
Kind: compiled

```gherkin
Given one product capability with no realizing component
When build_corpus_graph runs
Then aggregates.orphan_capability_rate reflects that one orphan
```

### AC-GRAPH-005
Covers: R-GRAPH-005
Kind: compiled

```gherkin
Given one declared var with no component referencing it via uses_var
When build_corpus_graph runs
Then aggregates.orphan_var_rate reflects that one orphan
```

### AC-GRAPH-006
Covers: R-GRAPH-006
Kind: compiled

```gherkin
Given a successful build
When the output location is checked
Then it is exactly verification/corpus-graph.json, with no second file
  produced elsewhere
```

### AC-GRAPH-007
Covers: R-GRAPH-007
Kind: compiled

```gherkin
Given a merge to main
When the pipeline runs
Then corpus-graph.json is rebuilt as part of that merge, not deferred to a
  later scheduled job
```

### AC-GRAPH-008
Covers: R-GRAPH-008
Kind: compiled

```gherkin
Given unchanged corpus, provenance, and verification state
When build_corpus_graph runs twice
Then the two resulting files are byte-identical
```
