# AC-GATE-002a

Covers: R-GATE-002
Kind: generated-test

```gherkin
Given a provenance miss, a faked generator returning one file, and a
  faked verifier-orchestrator whose verify calls the test_author it
  receives with a sentinel bundle, and the judge it receives with a
  CriterionBundle-shaped dict
When run_component_gates("comp-foo", repo_root, "m", seed=3,
  llm_backend=<sentinel backend>) is called
Then the faked test-author's author_test received that sentinel
  bundle, model "m", seed 3, and the sentinel backend, and the faked
  llm-endpoint's complete received model "m" and the sentinel backend
```
