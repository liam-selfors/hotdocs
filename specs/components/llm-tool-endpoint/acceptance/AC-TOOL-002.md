# AC-TOOL-002

Covers: R-TOOL-002
Kind: generated-test

```gherkin
Given ANTHROPIC_API_KEY is "k", a tool list with one tool named
  "write_file", an execute that records its calls and returns ("ok",
  False), and urllib.request.urlopen replaced by a function that records
  each request and replies first {"content": [{"type": "text", "text":
  "writing"}, {"type": "tool_use", "id": "t1", "name": "write_file",
  "input": {"path": "a.py"}}], "stop_reason": "tool_use"} and then
  {"content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn"}
When run_tool_loop("sys", "go", "anthropic:claude-opus-5-5", tools,
  execute) is called
Then execute was called once with ("write_file", {"path": "a.py"}); the
  first request went to https://api.anthropic.com/v1/messages with
  tool_choice {"type": "auto"}, no temperature key, and system text
  "sys"; the second request's last message is a user message whose
  content is [{"type": "tool_result", "tool_use_id": "t1", "content":
  "ok"}]; and the result has text "done", turns 2, tool_calls 1 and stop
  "end_turn"

Given the same setup but the first reply's stop_reason is "max_tokens"
When run_tool_loop is called
Then stop is "truncated", turns is 1, and execute was never called
```
