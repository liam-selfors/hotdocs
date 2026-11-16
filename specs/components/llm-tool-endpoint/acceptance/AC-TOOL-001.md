# AC-TOOL-001

Covers: R-TOOL-001
Kind: generated-test

```gherkin
Given urllib.request.urlopen replaced by a function that records calls
When run_tool_loop("s", "p", "gemini:g", [], execute) is called, and
  separately with model "ollama:llama3.2"
Then each raises ToolUseUnsupported and no request was recorded

Given ANTHROPIC_API_KEY is not set in the environment
When run_tool_loop("s", "p", "anthropic:claude-opus-5-5", [], execute) is called
Then stop is "error", model_call_error's category is "auth", turns is 0,
  and no request was recorded
```
