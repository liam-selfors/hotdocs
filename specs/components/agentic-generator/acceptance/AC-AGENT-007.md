# AC-AGENT-007

Covers: R-AGENT-007
Kind: generated-test

```gherkin
Given a generator stand-in and a loop stand-in that calls write_file
  "work/a.py" and then raises RuntimeError("boom")
When generate_agentic is called
Then it raises RuntimeError, and afterwards neither a directory whose
  name starts "hotdocs-agent-" nor a file ending ".sb" whose name starts
  "hotdocs-agent-" exists under tempfile.gettempdir() that did not exist
  before the call
```
