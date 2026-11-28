---
id: P-COMPLIANCE-GATE
title: Secrets and Licensed-Code Risk Never Reach main Silently
status: draft
owners: [pipeline-team]
---

# Secrets and Licensed-Code Risk Never Reach main Silently

## Purpose

Secrets and license/similarity flags are compliance risk, not correctness
risk — handled automatically (no mandatory human sign-off to merge), but
never silently: every flag is recorded, surfaced in the review packet, and
above a severity threshold, actively pushed to a standing channel.

## Scope

In scope: `specs/`, `gen/`, and `verification/`, scanned pre-merge-gate and
(where tooling allows) as early as pre-commit/pre-push. Out of scope:
deployment-time config values and infra-as-code, which never enter the spec
corpus at all and so aren't this capability's concern.

## Capability scenario

### CS-COMPLIANCE-001
Covers: P-COMPLIANCE-GATE
Kind: generated-test

```gherkin
Given generated code that matches a known-licensed-code fingerprint above the
  similarity threshold, and any stand-in provenance-tracker whose
  check_readiness returns a VerifyReport whose "components" and
  "capabilities" are mappings keyed by id, never lists, each component's
  entry carrying the license_scan its provenance manifest records at
  the time of the call (the review packet reads the flag from there,
  never from the manifest itself)
When the pipeline's license scan runs
Then the merge is blocked, the result is written into the provenance
  manifest's license_scan field regardless of outcome, and the finding
  appears in the review packet built after that run, also when the run's
  generation loop retried an earlier attempt that failed verification
  before the candidate the scan blocked (a later, separate run whose scan
  is clean replaces the manifest's license_scan, and its packet shows
  that clean result)
```
