---
id: comp-impact-analyzer-acceptance
title: Impact Analyzer — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Impact Analyzer — Acceptance Criteria

Every criterion below is `kind: compiled` — blast-radius computation is a
pure graph traversal over corpus state, the same demonstration `spec-linter`
already made for D5's "prefer `compiled` whenever possible" guidance, applied
to a second real component.

### AC-IMPACT-001
Covers: R-IMPACT-001
Kind: compiled

```gherkin
Given a changed spec id for component comp-foo
When hotdocs impact --changed comp-foo runs
Then the report's impacted list contains comp-foo with reason "direct"
```

### AC-IMPACT-002
Covers: R-IMPACT-002
Kind: compiled

```gherkin
Given comp-foo's spec.md changed but its interface.md is byte-identical to
  the prior commit, and comp-bar depends_on comp-foo
When hotdocs impact --changed comp-foo runs
Then the report's impacted list contains comp-foo with reason "direct" and
  does NOT contain comp-bar
```

### AC-IMPACT-003
Covers: R-IMPACT-003
Kind: compiled

```gherkin
Given comp-foo's interface.md changed relative to the prior commit, and
  comp-bar depends_on comp-foo
When hotdocs impact --changed comp-foo runs
Then the report's impacted list contains comp-bar with reason
  "transitive-interface" and via "comp-foo"
```

### AC-IMPACT-004
Covers: R-IMPACT-004
Kind: compiled

```gherkin
Given VAR-CACHE-STORE-URL changed, and comp-cache-manager has
  uses_var: [VAR-CACHE-STORE-URL]
When hotdocs impact --changed VAR-CACHE-STORE-URL runs
Then the report's impacted list contains comp-cache-manager with reason
  "transitive-var" and via "VAR-CACHE-STORE-URL"
```

### AC-IMPACT-005
Covers: R-IMPACT-005
Kind: compiled

```gherkin
Given P-ZERO-EDIT's golden scenarios changed, and comp-foo has
  realizes: [P-ZERO-EDIT]
When hotdocs impact --changed P-ZERO-EDIT runs
Then the report's impacted list contains comp-foo with reason
  "transitive-capability" and via "P-ZERO-EDIT"
```

### AC-IMPACT-006
Covers: R-IMPACT-006
Kind: compiled

```gherkin
Given an unchanged corpus and the same --changed argument
When hotdocs impact runs twice in a row
Then both runs produce byte-identical BlastRadiusReport output
```

### AC-IMPACT-007
Covers: R-IMPACT-007
Kind: compiled

```gherkin
Given a corpus containing a dangling depends_on reference unrelated to the
  changed ids
When hotdocs impact --changed comp-foo runs
Then the report's precondition_error is non-null, impacted is empty, and the
  CLI exits with code 1
```
