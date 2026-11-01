# AC-GATE-002b

Covers: R-GATE-002
Kind: generated-test

```gherkin
Given a provenance miss and a faked generator returning one file
When run_component_gates("comp-foo", repo_root, "m",
  retry_feedback=["R-FOO-002"]) is called
Then the invocation log shows assemble, generate, and verify in that
  order, assemble received mode "cold", and generate received the
  assembled bundle, model "m", and ["R-FOO-002"]
```
