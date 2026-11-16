# AC-GEN-021

Covers: R-GEN-015
Kind: generated-test

```gherkin
Given a cold-mode SpecBundle for comp-foo-bar and a mock model whose
  response returns the files "foo-bar/foo_bar.py",
  "gen/foo-bar/helpers/__init__.py", and "foo_bar_extra.py"
When generate is called with that bundle
Then gen/foo-bar/foo_bar.py, gen/foo-bar/helpers/__init__.py, and
  gen/foo-bar/foo_bar_extra.py exist, and nothing is written under
  gen/foo-bar/foo-bar/ or gen/foo-bar/gen/
```
