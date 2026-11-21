# R-TOOL-002

**R-TOOL-002** — For `anthropic`, `run_tool_loop` MUST send each turn as
  the wire-format document's request, the first with `messages`
  `[{"role": "user", "content": prompt}]`, and act on each reply's
  `stop_reason` as its table says: on `tool_use` it calls `execute` once
  for each `tool_use` block, in order, then appends the reply's `content`
  as the assistant message and one user message holding every
  `tool_result` in the same order, `is_error: true` present exactly for
  an error result, and sends the next turn.
