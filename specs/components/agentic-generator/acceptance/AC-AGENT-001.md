# AC-AGENT-001

Covers: R-AGENT-001
Kind: generated-test

```gherkin
Given a generator stand-in whose check_write_allowed returns
  "sealed-component" and a loop stand-in that records whether it was
  called
When generate_agentic({"component_id": "comp-widget", "spec_bundle_hash":
  "sha256:x", "hint_code": None}, "m", repo_root=<tmp>) is called
Then the result's refused is "sealed-component", mode is "agentic",
  turns is 0, the loop stand-in was never called, and no directory
  whose name starts "hotdocs-agent-" exists under tempfile.gettempdir()

Given a generator stand-in and <tmp>/NO_ENV created
When generate_agentic is called the same way
Then the result's model_call_error is {"category": "environment",
  "message": "fake needs fakeprog >= 2"}, turns is 0 and the loop
  stand-in was never called
```
