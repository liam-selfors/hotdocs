# AC-GEN-013

Covers: R-GEN-012
Kind: generated-test

```gherkin
Given a cold-mode SpecBundle, retry_feedback=["R-FOO-003"], and a mock
  model that records what it was sent
When generate is called with these inputs
Then the mock model's recorded input contains retry_feedback as a
  distinctly labeled section containing only "R-FOO-003" — no Gherkin
  text, rationale, or expected/actual values anywhere in the prompt —
  and the resulting GenerationResult's retry_feedback field echoes
  ["R-FOO-003"]
```
