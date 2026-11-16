# AC-TOOL-004

Covers: R-TOOL-004
Kind: generated-test

```gherkin
Given ANTHROPIC_API_KEY is "k", one tool named "boom", an execute that
  raises ValueError("bad"), and scripted anthropic replies whose first
  holds three tool_use blocks, {"id": "a", "name": "boom", "input": {}},
  {"id": "b", "name": "nope", "input": {}} and {"id": "c", "name": "boom",
  "input": "text"}, with stop_reason "tool_use", and whose second ends
  the turn
When run_tool_loop("sys", "go", "anthropic:claude-opus-5-5", tools,
  execute) is called
Then execute was called once; the second request's tool results are, in
  order, "tool error: ValueError: bad", "unknown tool: nope" and
  "arguments must be a JSON object", each with is_error true; and stop is
  "end_turn"
```
