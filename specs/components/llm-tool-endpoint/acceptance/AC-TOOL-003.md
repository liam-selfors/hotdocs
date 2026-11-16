# AC-TOOL-003

Covers: R-TOOL-003
Kind: generated-test

```gherkin
Given OPENAI_API_KEY is "k", one tool named "read_file", an execute
  returning ("contents", False), and urllib.request.urlopen replaced by a
  function that records each request and replies first {"choices":
  [{"message": {"role": "assistant", "content": null, "tool_calls":
  [{"id": "c1", "type": "function", "function": {"name": "read_file",
  "arguments": "{\"path\": \"x\"}"}}]}, "finish_reason": "tool_calls"}]}
  and then {"choices": [{"message": {"role": "assistant", "content":
  "fin"}, "finish_reason": "stop"}]}
When run_tool_loop("sys", "go", "openai:gpt-6-astra", tools, execute)
  is called
Then the first request went to https://api.openai.com/v1/chat/completions,
  its messages begin with {"role": "system", "content": "sys"}, and its
  tools[0] is {"type": "function", "function": {"name": "read_file", ...}};
  the second request's last message is {"role": "tool", "tool_call_id":
  "c1", "content": "contents"}; and the result has text "fin" and stop
  "end_turn"

Given the first reply's finish_reason is "length"
When run_tool_loop is called
Then stop is "truncated"
```
