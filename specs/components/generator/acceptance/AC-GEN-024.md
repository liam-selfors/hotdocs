# AC-GEN-024

Covers: R-GEN-021
Kind: generated-test

```gherkin
Given repo_root holds comp-widget-maker declaring
  assets [fake:static/app.txt] and the fake kind (testing.md), and a
  mock reply with complete blocks for widget_maker.py only
When generate is called
Then model_call_error is {"category": "missing_asset", "message":
  "missing asset: static/app.txt"}, files is empty, gen/widget-maker/
  is not created, and nothing is cached

Given the reply instead has blocks for widget_maker.py and
  static/app.txt holding "bad"
When generate is called
Then model_call_error is {"category": "malformed_layout", "message":
  "static/app.txt: bad"} and nothing is written or cached

Given the reply instead has blocks for widget_maker.py holding "A = 1"
  and widget-maker/static/app.txt holding "ok"
When generate is called
Then the result has no model_call_error, files is {"widget_maker.py":
  "A = 1", "static/app.txt": "ok"}, and gen/widget-maker/static/app.txt
  holds "ok"

Given the component declares assets [nosuchkind:static/app.txt] and the
  reply has blocks for widget_maker.py and static/app.txt holding "ok"
When generate is called
Then model_call_error is {"category": "environment", "message":
  "unknown asset kind: nosuchkind"} and nothing is written or cached
```
