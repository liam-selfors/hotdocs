# AC-TOOL-007

Covers: R-TOOL-007
Kind: generated-test

```gherkin
Given a fake claude script (interface/library.md's Test fixtures) that
  records its argv to a file, sends one tools/call for "write_file" with
  arguments {"path": "a.py"}, writes that call's reply line to a file,
  and prints a result line with result "all done" and num_turns 3, and an
  execute that records its calls and returns ("wrote a.py", False)
When run_tool_loop("sys", "go", "claude-cli:claude-opus-5-5",
  [write_file tool], execute, claude_command=<fake path>) is called
Then execute was called once with ("write_file", {"path": "a.py"}); the
  recorded reply's result is {"content": [{"type": "text", "text":
  "wrote a.py"}], "isError": false}; the recorded argv holds "--tools"
  followed by "", "--strict-mcp-config", "--setting-sources" followed by
  "", "--disable-slash-commands", "--allowedTools" followed by
  "mcp__hotdocs__write_file", "--max-turns" followed by "40", and never
  "--safe-mode"; and the result has text "all done", turns 3, tool_calls
  1 and stop "end_turn"

Given a fake claude that prints a result line with subtype
  "error_max_turns"
When run_tool_loop is called with it
Then stop is "budget_exhausted"

Given a fake claude that exits 1 with no result line
When run_tool_loop is called with it
Then stop is "error" and model_call_error's category is "network"
```
