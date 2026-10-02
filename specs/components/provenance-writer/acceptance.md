---
id: comp-provenance-writer-acceptance
title: Provenance Writer — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Provenance Writer — Acceptance Criteria

All eleven criteria are `kind: compiled` — collecting and writing already-
produced results is pure, deterministic logic. A seventh component in this
corpus with a fully `compiled` acceptance set.

### AC-PROV-001
Covers: R-PROV-001
Kind: compiled

```gherkin
Given a complete set of ProvenanceInputs
When write_provenance runs
Then the written manifest's top-level keys exactly match SPEC_GUIDELINES.md
  §8's field list — no extra keys, no missing ones
```

### AC-PROV-002
Covers: R-PROV-002
Kind: compiled

```gherkin
Given a GenerationResult with model "claude-sonnet-5" and seed 2
When write_provenance runs
Then model_pin is "claude-sonnet-5" and sample_index is 2
```

### AC-PROV-003
Covers: R-PROV-003
Kind: compiled

```gherkin
Given reported versions from cache-manager, criterion-compiler, and
  license-scanner
When write_provenance runs
Then gate_versions contains exactly those three reported values, unmodified
```

### AC-PROV-004
Covers: R-PROV-004
Kind: compiled

```gherkin
Given a GenerationResult with cache_hit true
When write_provenance runs
Then the manifest's cache_hit is true
```

### AC-PROV-005
Covers: R-PROV-005
Kind: compiled

```gherkin
Given a VerificationReport with overall "fail"
When write_provenance runs
Then verification_report in the manifest contains that full report, not a
  summary of it
```

### AC-PROV-006
Covers: R-PROV-006
Kind: compiled

```gherkin
Given no CrossCheckResult was provided (the gate did not run)
When write_provenance runs
Then cross_model_check is the literal string "not-run", not absent from the
  manifest
```

### AC-PROV-007
Covers: R-PROV-007
Kind: compiled

```gherkin
Given a clean LicenseScanResult and a clean SecretScanResult
When write_provenance runs
Then both license_scan and secret_scan are present in the manifest, even
  though neither flagged anything
```

### AC-PROV-008
Covers: R-PROV-008
Kind: compiled

```gherkin
Given a GenerationResult carrying an unrelated internal timestamp
When write_provenance runs
Then generated_at reflects this component's own write time, not that
  internal timestamp
```

### AC-PROV-009
Covers: R-PROV-009
Kind: compiled

```gherkin
Given cache_hit is true and a matching prior commit's manifest exists
When write_provenance runs
Then verification_report, cross_model_check, license_scan, and secret_scan
  are copied verbatim from that prior manifest, not freshly computed
```

### AC-PROV-010
Covers: R-PROV-010
Kind: compiled

```gherkin
Given a completed write_provenance call
When both gen/<component>/.provenance.json and
  verification/<component>/.provenance.json are read back
Then their contents are byte-identical
```

### AC-PROV-011
Covers: R-PROV-011
Kind: compiled

```gherkin
Given a completed write_provenance call
When the written file is parsed as JSON
Then parsing succeeds and its key set matches the schema exactly
```
