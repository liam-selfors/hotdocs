# AC-VERIFY-022

Covers: R-VERIFY-014
Kind: generated-test

```gherkin
Given an unsealed component whose verification/<slug>/conftest.py puts
  the absolute path of its gen/<slug>/ directory first on sys.path and
  imports its module, and one generated test that fails on every
  mutant of its one function
When verify runs
Then mutation_score is 1.0
```
