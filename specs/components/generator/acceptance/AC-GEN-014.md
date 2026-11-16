# AC-GEN-014

Covers: R-GEN-013
Kind: generated-test

```gherkin
Given a cold-mode SpecBundle whose dependency_usage names one real
  dependency's importable module and function signature, and a mock
  model that records what it was sent
When generate is called with that bundle
Then the mock model's recorded input contains dependency_usage as a
  distinctly labeled section, separate from dependency_interfaces
```
