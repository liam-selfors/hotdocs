---
id: comp-cache-manager-acceptance
title: Cache Manager — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Cache Manager — Acceptance Criteria

Every criterion below is `kind: compiled` — a third real component, after
`spec-linter` and `impact-analyzer`, whose entire behavior is deterministic
store logic with no model call anywhere in it.

### AC-CACHE-001
Covers: R-CACHE-001
Kind: compiled

```gherkin
Given no entry stored for a given cache key
When get is called with that key
Then it returns Miss, not an error and not a partial result
```

### AC-CACHE-002
Covers: R-CACHE-002
Kind: compiled

```gherkin
Given the same four key components (spec_bundle_hash, gate_inputs_hash,
  gate_version, model_pin) supplied by two different calling components
When each computes the cache key for a put
Then both produce byte-identical serialized keys
```

### AC-CACHE-003
Covers: R-CACHE-003
Kind: compiled

```gherkin
Given two concurrent put calls for the same cache key with identical result
  payloads (as determinism requires)
When both complete
Then a subsequent get for that key returns a result equal to both payloads,
  with no corruption or partial write
```

### AC-CACHE-004
Covers: R-CACHE-004
Kind: compiled

```gherkin
Given the backing store at VAR-CACHE-STORE-URL is unreachable
When get is called with any key
Then it returns Miss rather than raising an exception
```

### AC-CACHE-005
Covers: R-CACHE-005
Kind: compiled

```gherkin
Given an entry stored under gate_version "license_scanner@1.0.0"
When get is called with the same spec_bundle_hash/gate_inputs_hash/model_pin
  but gate_version "license_scanner@2.0.0"
Then it returns Miss, not the entry stored under the old gate_version
```

### AC-CACHE-006
Covers: R-CACHE-006
Kind: compiled

```gherkin
Given a stored entry
When hotdocs cache inspect runs with that entry's key components
Then it reports "hit" and prints the entry's provenance-relevant fields
```

### AC-CACHE-007
Covers: R-CACHE-007
Kind: compiled

```gherkin
Given a put call whose payload shape does not match the schema for the
  cache_key's declared gate_version (e.g. a LintReport payload under a
  license_scanner gate_version)
When put is called
Then it is rejected with a schema-validation error and nothing is stored
```
