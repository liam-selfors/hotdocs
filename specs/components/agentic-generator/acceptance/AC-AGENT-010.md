# AC-AGENT-010

Covers: R-AGENT-005
Kind: generated-test

```gherkin
Given a generator stand-in and a loop stand-in whose script writes
  "work/widget_maker.py" with "A = 1" and "work/static/app.txt" with
  "bad", then calls finish
When generate_agentic(bundle for comp-widget-maker, "m",
  repo_root=<tmp>) is called
Then model_call_error is {"category": "malformed_layout", "message":
  "static/app.txt: bad"}, files is {}, mode is "agentic", write_files
  was never called, and check_assets was called once with
  "comp-widget-maker", {"widget_maker.py": "A = 1", "static/app.txt":
  "bad"} and repo_root <tmp>

Given the script writes "ok" to "work/static/app.txt" instead
When generate_agentic is called
Then the result has files {"widget_maker.py": "A = 1",
  "static/app.txt": "ok"}, no model_call_error, and write_files was
  called once with those files
```
