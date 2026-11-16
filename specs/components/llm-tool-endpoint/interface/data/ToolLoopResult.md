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

- `text` is the model's final text: for `anthropic`, the `text` blocks
  of the last reply joined with no separator; for `openai` and
  `openai-compatible`, the last reply's `choices[0].message.content`;
  for `claude-cli`, the result's `result`; `""` when there is none or it
  is `null`.
- `transcript` is the HTTP loop's `messages` list as sent, the last
  reply's assistant message appended; for `claude-cli`, the parsed
  stream-json events in order.
- `turns` is the number of model requests made, the one whose reply
  ended the loop included; for `claude-cli`, the result's
  `num_turns`.
- `tool_calls` is the number of calls passed to `execute`, whether it
  returned or raised; a call `R-TOOL-004` rejects before `execute`, or
  one past the tool-call cap, is not counted. This holds for
  `claude-cli` too.
- `stop` is one of `end_turn`, `truncated`, `refusal`,
  `budget_exhausted`, `error`.
- `model_call_error` is `null` unless `stop` is `error`; then it is
  `{"category": ..., "message": ...}` with `llm-endpoint`'s categories
  (`network`, `auth`, `rate_limit`, `timeout`).
