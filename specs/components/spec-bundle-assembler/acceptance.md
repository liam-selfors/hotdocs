---
id: comp-spec-bundle-assembler-acceptance
title: Spec Bundle Assembler — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Spec Bundle Assembler — Acceptance Criteria

Every criterion is `kind: compiled` — reading, concatenating, and hashing
files is pure, deterministic logic; nothing here needs a model or judgment.
The third component in this corpus for which that's true of 100% of its
acceptance criteria.

### AC-ASSEMBLE-001
Covers: R-ASSEMBLE-001
Kind: compiled

```gherkin
Given a component with spec.md, interface.md, constraints.md, and
  acceptance.md
When assemble runs in cold mode for that component
Then the resulting SpecBundle contains spec, interface, and constraints, and
  contains no field derived from acceptance.md
```

### AC-ASSEMBLE-002
Covers: R-ASSEMBLE-002
Kind: compiled

```gherkin
Given a component that depends_on another component with its own spec.md,
  interface.md, and constraints.md
When assemble runs for the dependent component
Then dependency_interfaces contains only the dependency's interface.md
  content, and contains neither its spec.md nor its constraints.md
```

### AC-ASSEMBLE-003
Covers: R-ASSEMBLE-003
Kind: compiled

```gherkin
Given a component with uses_var: [VAR-FOO-URL]
When assemble runs for that component
Then the resulting SpecBundle's vars field contains VAR-FOO-URL's full
  declaration content
```

### AC-ASSEMBLE-004
Covers: R-ASSEMBLE-004
Kind: compiled

```gherkin
Given any component
When assemble runs for it
Then the resulting SpecBundle's glossary field equals the current content of
  specs/glossary.md exactly
```

### AC-ASSEMBLE-005
Covers: R-ASSEMBLE-005
Kind: compiled

```gherkin
Given a corpus with a hard-fail-severity spec-linter finding anywhere in it
When assemble runs for any component
Then assembly fails with a precondition-failure result, not a partial bundle
```

### AC-ASSEMBLE-006
Covers: R-ASSEMBLE-006
Kind: compiled

```gherkin
Given an unchanged corpus
When assemble runs twice for the same component
Then the two resulting SpecBundles are byte-identical
```

### AC-ASSEMBLE-007
Covers: R-ASSEMBLE-007
Kind: compiled

```gherkin
Given a component
When assemble runs for it
Then spec_bundle_hash is present and recomputing it from the bundle's own
  contents reproduces the same value
```

### AC-ASSEMBLE-008
Covers: R-ASSEMBLE-008
Kind: compiled

```gherkin
Given a component with existing gen/<component>/ content
When assemble runs in hint mode for that component
Then hint_code contains that content, keyed by relative path, and every
  other field matches what cold mode would have produced
```
