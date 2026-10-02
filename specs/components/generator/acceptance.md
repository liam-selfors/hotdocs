---
id: comp-generator-acceptance
title: Generator — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Generator — Acceptance Criteria

Mixed `kind`, and deliberately so: R-GEN-001–008 describe behavior around an
external model call, tested with an injected mock model (same
dependency-injection pattern `spec-linter`'s `judge` parameter already
established) — `generated-test`, not `compiled`, since exercising them means
setting up and asserting on a mocked call, not purely structural text/graph
analysis. R-GEN-009 is a pure path-safety check with no model involved at
all, and is `compiled` like everything in `spec-bundle-assembler`.

Whether R-GEN-001–008 could instead be `compiled` depends on whether
`criterion-compiler`'s step grammar grows mock/dependency-injection support
— left as an open question there, not forced here.

### AC-GEN-001
Covers: R-GEN-001
Kind: generated-test

```gherkin
Given a cold-mode SpecBundle and a mock model that records what it was sent
When generate is called with that bundle
Then the mock model's recorded input contains exactly the bundle's spec,
  interface, constraints, dependency_interfaces, vars, and glossary fields,
  and nothing else
```

### AC-GEN-002
Covers: R-GEN-002
Kind: generated-test

```gherkin
Given a hint-mode SpecBundle (hint_code populated) and a mock model that
  records what it was sent
When generate is called with that bundle
Then the mock model's recorded input contains hint_code as a distinctly
  labeled section, separate from the cold bundle fields
```

### AC-GEN-003
Covers: R-GEN-003
Kind: generated-test

```gherkin
Given any SpecBundle
When generate is called
Then the resulting GenerationResult's prompt_version matches the frozen
  template's declared version
```

### AC-GEN-004
Covers: R-GEN-004
Kind: generated-test

```gherkin
Given the same SpecBundle and two different model identifiers
When generate is called once with each
Then the mock model recorded for each call receives the model identifier
  passed to that call, not a hardcoded default
```

### AC-GEN-005
Covers: R-GEN-005
Kind: generated-test

```gherkin
Given a cache-manager pre-populated with a result for a given
  (spec_bundle_hash, gate_inputs_hash, gate_version, model_pin) key
When generate is called with inputs matching that key
Then the cached result is returned and the mock model is never called
```

### AC-GEN-006
Covers: R-GEN-006
Kind: generated-test

```gherkin
Given an empty cache and a mock model that returns a fixed result
When generate is called
Then cache-manager contains that result under the correct key afterward
```

### AC-GEN-007
Covers: R-GEN-007
Kind: generated-test

```gherkin
Given a call to generate with seed=3
When the call completes
Then the resulting GenerationResult's seed field is 3
```

### AC-GEN-008
Covers: R-GEN-008
Kind: generated-test

```gherkin
Given a mock model that raises a network error
When generate is called
Then the resulting GenerationResult has a non-null model_call_error, an
  empty files field, and cache_hit is false
```

### AC-GEN-009
Covers: R-GEN-009
Kind: compiled

```gherkin
Given a component marked sealed: true with a source_path, and a second
  component with a gen/<component>/.overrides.json listing one pinned file
When generate is invoked for either component
Then generate refuses to write under that source_path, and refuses to
  overwrite the pinned file, in both cases without needing to call a model
  to know this
```
