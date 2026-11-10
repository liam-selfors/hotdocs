# AC-ENDPOINT-012

Covers: R-ENDPOINT-003
Kind: generated-test

```gherkin
Given VAR_HOTDOCS_CONFIG unset, an empty current directory, and the
  claude command replaced by a recorder that exits 0 printing these
  lines: {"type": "system"}, {"type": "assistant", "message": {"content":
  [{"type": "text", "text": "ab"}]}}, {"type": "assistant", "message":
  {"content": [{"type": "thinking"}, {"type": "text", "text": "cd"}]}},
  {"type": "result", "is_error": false}
When complete("hi", "claude-sonnet-5") is called
Then its text is "abcd", model_call_error is null, and the recorded
  command holds --output-format stream-json --verbose

Given the same recorder ending with {"type": "result", "is_error": true}
Then text is null and model_call_error is set

Given a recorder whose whole stdout is "hello\n" and exits 0
Then text is exactly "hello\n"
```
