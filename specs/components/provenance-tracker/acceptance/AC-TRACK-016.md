# AC-TRACK-016

Covers: R-TRACK-016
Kind: generated-test

The corpus is comp-plain alone, not sealed. Its faked check_provenance
is a hit with overall "pass", license_scan {"blocked": false} and a
stored secret_scan {"flagged": true, "matches": []}.

```gherkin
Given the stand-in returns {"flagged": false, "matches": []}
When check_readiness(repo_root) is called
Then ready is true, not_ready_reasons is [], the stand-in logged
  exactly one call, str(repo_root), secret_scan is {"flagged": false,
  "matches": []}, and components["comp-plain"]["secret_scan"] is the
  stored one, unchanged

Given the stand-in returns the flagged result
When check_readiness(repo_root) is called
Then ready is false and not_ready_reasons is exactly ["secret_scan
  flagged: a/b.py:3 AWS Access Key"]

Given the stand-in's scan raises RuntimeError("boom")
When check_readiness(repo_root) is called
Then it does not raise, secret_scan is null, and not_ready_reasons is
  exactly ["secret_scan unavailable: RuntimeError: boom"]

Given changed_ids and impact-analyzer reporting a precondition_error
When check_readiness is called with those changed_ids
Then the stand-in was never called and secret_scan is null
```
