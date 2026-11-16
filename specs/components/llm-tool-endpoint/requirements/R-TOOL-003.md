# R-TOOL-003

**R-TOOL-003** — For `openai` and `openai-compatible`, `run_tool_loop`
  MUST send each turn as the wire-format document's request, the first
  with `messages` holding the system message then
  `{"role": "user", "content": prompt}`, and act on `finish_reason` as its
  table says: on `tool_calls` it calls `execute` once per call, in order,
  with the call's `arguments` parsed by `json.loads`, then appends the
  reply's message and one `{"role": "tool", "tool_call_id", "content"}`
  message per call in the same order, and sends the next turn.
