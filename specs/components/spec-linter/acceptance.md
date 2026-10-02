---
id: comp-spec-linter-acceptance
title: Spec Linter — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Spec Linter — Acceptance Criteria

Every criterion below is `kind: compiled` — nothing in this component's
behavior is runtime-behavior-of-generated-code or a judgment call; it is all
deterministic, rule-based logic over spec text, so none of it needs a second
model or an `llm-judge` evaluator. (A deliberate test of D5's own guidance:
"prefer `compiled` whenever the criterion is in principle about runtime
behavior... reach for `llm-judge` only for criteria no code test could
capture" — a linter is the cleanest possible case for that guidance to hold.)

### AC-LINT-001
Covers: R-LINT-001
Kind: compiled

```gherkin
Given a component spec.md with no `owners` field in its frontmatter
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-001
```

### AC-LINT-002
Covers: R-LINT-002
Kind: compiled

```gherkin
Given a component spec.md with status: ratified and a non-empty
  "Open questions" section
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-002
```

### AC-LINT-003
Covers: R-LINT-003
Kind: compiled

```gherkin
Given a component spec.md whose depends_on lists an id with no corresponding
  spec file anywhere under specs/
When hotdocs lint runs
Then the report contains a fail-severity finding for rule R-LINT-003 naming
  the dangling id
```

### AC-LINT-004
Covers: R-LINT-004
Kind: compiled

```gherkin
Given two component specs whose depends_on entries form a cycle (A depends_on
  B, B depends_on A)
When hotdocs lint runs against the corpus
Then the report contains a fail-severity finding for rule R-LINT-004 naming
  both components
```

### AC-LINT-005
Covers: R-LINT-005
Kind: compiled

```gherkin
Given a component spec.md with sealed: true and no source_path field
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-005
```

### AC-LINT-006
Covers: R-LINT-006
Kind: compiled

```gherkin
Given a component spec.md with sealed: false (or absent) and zero realizes
  entries
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-006
```

### AC-LINT-007
Covers: R-LINT-007
Kind: compiled

```gherkin
Given a Behavior section containing a requirement bullet with no RFC 2119
  keyword in its text
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-007
```

### AC-LINT-008
Covers: R-LINT-008
Kind: compiled

```gherkin
Given a requirement R-FOO-001 with zero acceptance criteria whose Covers: tag
  names it
When hotdocs lint runs against the component
Then the report contains a fail-severity finding for rule R-LINT-008 naming
  R-FOO-001
```

### AC-LINT-009
Covers: R-LINT-009
Kind: compiled

```gherkin
Given an acceptance criterion with Covers: R-DOES-NOT-EXIST
When hotdocs lint runs against the component
Then the report contains a fail-severity finding for rule R-LINT-009
```

### AC-LINT-010
Covers: R-LINT-010
Kind: compiled

```gherkin
Given an acceptance criterion block missing a Kind: tag
When hotdocs lint runs against the component
Then the report contains a fail-severity finding for rule R-LINT-010
```

### AC-LINT-011
Covers: R-LINT-011
Kind: compiled

```gherkin
Given a component's Definitions section whose entry for a glossary term is a
  near-verbatim copy (token-overlap ratio >= 0.8) of that term's definition in
  specs/glossary.md
When hotdocs lint runs against the component
Then the report contains a fail-severity finding for rule R-LINT-011
```

### AC-LINT-011b
Covers: R-LINT-011
Kind: compiled

```gherkin
Given a component's Definitions section whose entry for a glossary term adds
  genuinely new, component-specific nuance with low textual overlap against
  the glossary's definition
When hotdocs lint runs against the component
Then the report contains no R-LINT-011 finding — this is a permitted delta,
  not a redefinition
```

### AC-LINT-012
Covers: R-LINT-012
Kind: compiled

```gherkin
Given a component whose generated-code LOC estimate exceeds 1500
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-012 citing
  the "Generated code per component" dimension
```

### AC-LINT-013
Covers: R-LINT-013
Kind: compiled

```gherkin
Given a specs/vars/ declaration with sensitivity: secret and a default field
  present
When hotdocs lint runs against it
Then the report contains a fail-severity finding for rule R-LINT-013
```

### AC-LINT-014
Covers: R-LINT-014
Kind: compiled

```gherkin
Given two files under specs/ that both declare themselves a corpus glossary,
  with no architecture/ spec recording a bounded-context split decision
When hotdocs lint runs against the corpus
Then the report contains a fail-severity finding for rule R-LINT-014
```

### AC-LINT-015
Covers: R-LINT-015
Kind: llm-judge

The one criterion in this component that is not `kind: compiled` or
`generated-test` — by design, matching D5's own guidance that `llm-judge` is
for qualities no test could capture even in principle. Detecting a
*structural* restatement (R-LINT-011) is mechanical; detecting that two
differently-worded passages mean *conflicting* things is not.

```gherkin
Given a component's Definitions section whose entry for a glossary term uses
  substantially different wording from specs/glossary.md's definition (so
  R-LINT-011's textual-similarity check does not fire), but asserts something
  that actually contradicts that definition
When hotdocs lint runs against the component with a model configured
Then the report contains a fail-severity finding for rule R-LINT-015, with a
  structured rationale explaining the conflict
```

### AC-LINT-015b
Covers: R-LINT-015
Kind: llm-judge

```gherkin
Given no model is configured for the linter at all
When hotdocs lint runs against a component with a Definitions-section entry
  that would otherwise need an R-LINT-015 judgment
Then R-LINT-015 is skipped with a visible, non-silent notice in the report —
  neither treated as passing nor causing a crash
```
