---
id: comp-test-author-acceptance
title: Test Author — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Test Author — Acceptance Criteria

Mixed `kind`, mirroring `generator`'s own split: behavior around the
external model call is `generated-test` (exercised via an injected mock
model, same pattern `generator`'s own suite already established);
R-AUTHOR-002 and R-AUTHOR-006 are pure path/data-safety checks, `compiled`.

### AC-AUTHOR-001
Covers: R-AUTHOR-001
Kind: generated-test

```gherkin
Given a CriterionBundle and a mock model that records what it was sent
When author_test is called
Then the mock model's recorded input contains the criterion text, the
  covered requirement's text, the interface, and the glossary
```

### AC-AUTHOR-002
Covers: R-AUTHOR-002
Kind: compiled

```gherkin
Given a CriterionBundle for a component with existing gen/<component>/
  content
When it is inspected
Then it contains no field derived from that gen/<component>/ content
```

### AC-AUTHOR-003
Covers: R-AUTHOR-003
Kind: generated-test

```gherkin
Given a second model is configured and generator used model A for this
  component's current code
When author_test runs
Then it is called with a model other than A; and when no second model is
  configured, it is called with the canonical model alone
```

### AC-AUTHOR-004
Covers: R-AUTHOR-004
Kind: generated-test

```gherkin
Given a cache-manager pre-populated with a result for a given criterion
  content hash and model
When author_test is called with matching inputs
Then the cached result is returned and the mock model is never called
```

### AC-AUTHOR-005
Covers: R-AUTHOR-005
Kind: generated-test

```gherkin
Given an empty cache and a mock model that returns a fixed result
When author_test is called
Then cache-manager contains that result under the correct key afterward
```

### AC-AUTHOR-006
Covers: R-AUTHOR-006
Kind: compiled

```gherkin
Given a successful author_test call for a component
When the written file's path is inspected
Then it is under verification/<component>/generated-test/ and not under
  gen/<component>/ or criterion-compiler's own output directory
```

### AC-AUTHOR-007
Covers: R-AUTHOR-007
Kind: generated-test

```gherkin
Given a mock model that raises a network error
When author_test is called
Then the resulting TestAuthoringResult has a non-null model_call_error, a
  null file, and cache_hit is false
```

### AC-AUTHOR-008
Covers: R-AUTHOR-008
Kind: generated-test

```gherkin
Given a successful author_test call
When the TestAuthoringResult and any logs are inspected
Then neither VAR-ANTHROPIC-API-KEY's nor VAR-SECOND-MODEL-API-KEY's value
  appears anywhere in them
```
