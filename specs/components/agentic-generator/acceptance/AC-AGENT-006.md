# AC-AGENT-006

Covers: R-AGENT-006
Kind: generated-test

```gherkin
Given a generator stand-in and a loop stand-in whose script writes
  "work/widget.py" and never calls finish, returning stop <stop>
  and, for "error", model_call_error {"category": "rate_limit",
  "message": "m"}
When generate_agentic(bundle for comp-widget, ...) is called
Then files is empty, write_files was never called, and
  model_call_error's category is <category>

Examples:
  | stop             | category               |
  | budget_exhausted | agent_budget_exhausted |
  | end_turn         | agent_unfinished       |
  | error            | rate_limit             |
```
