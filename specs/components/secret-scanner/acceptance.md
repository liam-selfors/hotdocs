---
id: comp-secret-scanner-acceptance
title: Secret Scanner — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Secret Scanner — Acceptance Criteria

Every criterion is `kind: compiled` — pattern and entropy matching are
deterministic; nothing here needs a model or judgment.

### AC-SECRET-001
Covers: R-SECRET-001
Kind: compiled

```gherkin
Given a file under gen/ containing a string matching a known API-key shape
When a full secret-scan runs
Then that file is reported in matches
```

### AC-SECRET-002
Covers: R-SECRET-002
Kind: compiled

```gherkin
Given a full scan with at least one match
When secret-scan completes
Then flagged is true and the merge is reported as blocked
```

### AC-SECRET-003
Covers: R-SECRET-003
Kind: compiled

```gherkin
Given a full scan with zero matches
When secret-scan completes
Then a SecretScanResult recording the clean outcome is still written to the
  provenance manifest
```

### AC-SECRET-004
Covers: R-SECRET-004
Kind: compiled

```gherkin
Given a match against a high-risk_tier rule (e.g. a recognizable AWS
  access-key shape) and VAR-COMPLIANCE-WEBHOOK-URL configured
When secret-scan runs
Then a notification is sent, independent of whether a later retry scans
  clean
```

### AC-SECRET-004b
Covers: R-SECRET-004
Kind: compiled

```gherkin
Given a match against a low-risk_tier rule (a generic high-entropy
  heuristic) that nonetheless blocked the merge, and
  VAR-COMPLIANCE-WEBHOOK-URL configured
When secret-scan runs
Then a notification is still sent, because the match blocked the merge —
  independent of that rule's low risk_tier
```

### AC-SECRET-004c
Covers: R-SECRET-004
Kind: compiled

```gherkin
Given a clean scan with no match at all
When secret-scan runs
Then notified is false
```

### AC-SECRET-005
Covers: R-SECRET-005
Kind: compiled

```gherkin
Given cache-manager already holds a result for the exact full-scan cache key
When a full scan runs with matching inputs
Then the cached result is returned and no rescan is performed
```

### AC-SECRET-006
Covers: R-SECRET-006
Kind: compiled

```gherkin
Given a cached result under gate_version "secret_scanner@1.0.0" and the
  pattern database is updated to "secret_scanner@2.0.0"
When a full scan runs with the new gate_version
Then the stale cache entry is not reused and a fresh scan is performed
```

### AC-SECRET-007
Covers: R-SECRET-007
Kind: compiled

```gherkin
Given any full scan
When it completes
Then exactly one SecretScanResult is produced
```

### AC-SECRET-008
Covers: R-SECRET-008
Kind: compiled

```gherkin
Given a set of files passed via --files, not yet committed
When hotdocs secret-scan precommit runs against them
Then matching is performed against only those files, with no cache-manager
  lookup attempted
```

### AC-SECRET-009
Covers: R-SECRET-009
Kind: compiled

```gherkin
Given a first generation sample that scans flagged, and a retried sample
  that scans clean
When the final merge decision is made
Then both the original flagged SecretScanResult and the clean one are
  present in the record
```
