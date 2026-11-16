# AC-TOOL-005

Covers: R-TOOL-005
Kind: generated-test

```gherkin
Given ANTHROPIC_API_KEY is "k", one tool "t" (description "d",
  input_schema {"type": "object"}), an execute returning ("ok", False),
  and urllib.request.urlopen replaced by a function that records each
  request and always replies {"content": [{"type": "tool_use", "id":
  "u1", "name": "t", "input": {}}], "stop_reason": "tool_use"}
When run_tool_loop("sys", "go", "anthropic:claude-opus-5-5", tools,
  execute, max_turns=3) is called
Then exactly 3 requests were recorded, turns is 3, tool_calls is 3, and
  stop is "budget_exhausted"

Given the same setup
When run_tool_loop(..., max_turns=10, max_tool_calls=2) is called
Then execute was called exactly twice, tool_calls is 2, and stop is
  "budget_exhausted"

Given the same setup
When run_tool_loop(..., wall_seconds=0) is called
Then no request was recorded and stop is "budget_exhausted"
```
