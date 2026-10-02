---
id: comp-license-scanner-acceptance
title: License Scanner — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# License Scanner — Acceptance Criteria

Every criterion is `kind: compiled` — k-gram fingerprint hashing and
threshold comparison are deterministic; nothing here needs a model or
judgment.

### AC-LICENSE-001
Covers: R-LICENSE-001
Kind: compiled

```gherkin
Given gen/<component>/ content whose k-gram similarity to the reference
  corpus is at or above the configured block threshold
When license-scan runs
Then blocked is true and the merge is reported as blocked
```

### AC-LICENSE-002
Covers: R-LICENSE-002
Kind: compiled

```gherkin
Given gen/<component>/ content with no match against the reference corpus
When license-scan runs
Then a LicenseScanResult is still written into the provenance manifest,
  recording a clean result rather than omitting one
```

### AC-LICENSE-003
Covers: R-LICENSE-003
Kind: compiled

```gherkin
Given a similarity score at or above the severity threshold and
  VAR-COMPLIANCE-WEBHOOK-URL configured
When license-scan runs
Then a notification is sent to that webhook, independent of whether the
  merge is later unblocked by a retry
```

### AC-LICENSE-004
Covers: R-LICENSE-004
Kind: compiled

```gherkin
Given cache-manager already holds a result for the exact
  (spec_bundle_hash, gen_output_hash, gate_version, model_pin) key
When license-scan runs with matching inputs
Then the cached result is returned and no rescan is performed
```

### AC-LICENSE-005
Covers: R-LICENSE-005
Kind: compiled

```gherkin
Given a cached result under gate_version "license_scanner@1.0.0" and the
  reference corpus is updated to "license_scanner@2.0.0"
When license-scan runs with the new gate_version
Then the stale cache entry is not reused and a fresh scan is performed
```

### AC-LICENSE-006
Covers: R-LICENSE-006
Kind: compiled

```gherkin
Given any component
When license-scan runs
Then exactly one LicenseScanResult is produced for that component
```

### AC-LICENSE-007
Covers: R-LICENSE-007
Kind: compiled

```gherkin
Given a first generation sample that scans flagged, and a retried sample
  that scans clean
When the final merge decision is made
Then both the original flagged LicenseScanResult and the clean one are
  present in the record — the flagged one is not deleted or overwritten
```
