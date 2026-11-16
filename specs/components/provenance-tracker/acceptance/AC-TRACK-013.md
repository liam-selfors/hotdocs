# AC-TRACK-013

Covers: R-TRACK-009
Kind: generated-test

Every scenario fakes provenance-checker with current_sealed_key,
check_sealed_provenance, current_provenance_key, and check_provenance, each
appending its name and arguments to an invocation log file; current_sealed_key
returns a key for a sealed component and None for any other. Fixture components
live under specs/components/<slug>/component.md.

```gherkin
Given the whole corpus is comp-seal (sealed) and comp-plain (not), a
  faked check_sealed_provenance returning {"hit": true, "sealed": true,
  "reason": null, "verification_report": {"overall": "pass"},
  "license_scan": null, "secret_scan": null}, and a faked
  check_provenance hit with a passing report for comp-plain
When check_readiness(repo_root) is called
Then ready is true; check_sealed_provenance was called for comp-seal only
  and check_provenance and current_provenance_key for comp-plain only;
  components["comp-seal"] equals the faked SealedCheckResult; and
  component-gate-runner was never loaded

Given check_sealed_provenance returns hit false with reason
  "source_changed"
When check_readiness is called
Then ready is false and not_ready_reasons has one entry for comp-seal,
  exactly "comp-seal: sealed provenance source_changed — run hotdocs
  generate comp-seal"

Given the first scenario plus a whole-repository secret scan that is
  flagged (a faked secret-scanner stored result, if one is read at all)
When check_readiness is called
Then comp-seal is still ready: a sealed component's readiness is its
  SealedCheckResult alone
```
