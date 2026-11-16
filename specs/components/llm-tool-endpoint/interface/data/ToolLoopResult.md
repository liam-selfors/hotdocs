# `ToolLoopResult`

```json
{
  "text": "Done: wrote widget.py.",
  "transcript": [{"role": "user", "content": "..."}],
  "turns": 4,
  "tool_calls": 7,
  "stop": "end_turn",
  "model_call_error": null
}
```

A dataclass with these fields in this order, with a `to_dict()` giving
the JSON form.

- `text` is the model's final text: the `text` blocks of the last reply
  joined with no separator, or the `claude-cli` result's `result`; `""`
  when there is none.
- `transcript` is the HTTP loop's `messages` list as sent, the last
  reply's assistant message appended; for `claude-cli`, the parsed
  stream-json events in order.
- `stop` is one of `end_turn`, `truncated`, `refusal`,
  `budget_exhausted`, `error`.
- `model_call_error` is `null` unless `stop` is `error`; then it is
  `{"category": ..., "message": ...}` with `llm-endpoint`'s categories
  (`network`, `auth`, `rate_limit`, `timeout`).
