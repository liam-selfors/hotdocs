# AC-LOOP-002

Covers: R-LOOP-002
Kind: generated-test

```gherkin
Given a generate stand-in that always returns files {"widget.py": "X = 1"},
  a check_surface stand-in returning ok False then ok True, and a verify
  stand-in returning overall "pass"
When run_attempts("comp-widget", bundle, repo_root, "m") is called
Then the attempts are, in order, outcome "surface_failed" with
  surface_ok False and overall None, then outcome "passed" with
  surface_ok True and overall "pass"; verify was called once, with
  judge and test_author both callables
```
