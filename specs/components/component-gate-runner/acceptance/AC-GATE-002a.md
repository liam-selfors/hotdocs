# AC-GATE-002a

Covers: R-GATE-002
Kind: generated-test

```gherkin
Given a provenance miss and a faked generation-loop whose run_attempts
  records its arguments and returns one passing attempt
When run_component_gates("comp-foo", repo_root, "m", seed=3,
  llm_backend=<sentinel backend>, retry_feedback=["R-FOO-002"],
  max_attempts=2, mode="agentic", allow_unisolated_exec=True) is called
Then the invocation log shows assemble then run_attempts; assemble
  received mode "cold"; and run_attempts received "comp-foo", the
  assembled bundle, repo_root, "m", mode "agentic", max_attempts 2,
  retry_feedback ["R-FOO-002"], seed 3, the sentinel backend,
  allow_unisolated_exec True and a callable on_attempt
```
