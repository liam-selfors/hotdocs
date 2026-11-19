# AC-SCENARIO-007

Covers: R-SCENARIO-006
Kind: generated-test

```gherkin
Given a committed record that is a hit
When one byte of one file under a realizing component's code directory
  changes, even though no spec file changed
Then check_capability_provenance gives hit false

Given the same hit
When the capability's own specs/product file changes
Then check_capability_provenance gives hit false

Given the same hit
When the planted python adapter's provision reports versions
  {"python": "3.14.7"} instead of {}
Then check_capability_provenance gives hit false

Given the same hit
When a file in a component that does not realize the capability
  changes, or a __pycache__ file in a realizing component appears
Then check_capability_provenance still gives hit true

Given the hit and a call to run_capability_gates after the first change
When it completes
Then the scenarios were re-run and the record holds a content_hash
  different from before
```
