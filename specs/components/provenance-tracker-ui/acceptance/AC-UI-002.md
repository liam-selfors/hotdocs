# AC-UI-002

Covers: R-UI-002
Kind: generated-test

```gherkin
Given a faked provenance-tracker whose last_requirement_failures returns
  [] and whose check_readiness returns: comp-foo hit with a passing
  verification_report and unflagged scans; comp-bar hit with
  verification_report.overall "fail"; comp-qux hit and passing but
  license_scan.blocked true; comp-zed hit and passing, license_scan.blocked
  false, but with a stored secret_scan whose flagged is true; and capability P-ZERO-EDIT whose
  capability_scenario_report["P-ZERO-EDIT"].overall is "fail"
When render_tracker_ui runs
Then the returned snapshot's statuses are comp-foo "passing", comp-bar
  "failing", comp-qux "failing", comp-zed "passing", and P-ZERO-EDIT "failing", and each
  node element's data-status attribute and status-<status> class match
  its snapshot status
```
