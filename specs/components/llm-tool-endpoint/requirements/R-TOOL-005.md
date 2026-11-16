# R-TOOL-005

**R-TOOL-005** — `run_tool_loop` MUST enforce its budgets. Before a turn
  that would exceed `max_turns`, and before executing a tool call that
  would exceed `max_tool_calls`, it stops with `stop` `budget_exhausted`
  and makes no further request or call. The tool calls of the
  `max_turns`-th reply still run, within `max_tool_calls`; the loop then
  stops before sending their results. Each HTTP request's timeout is
  the smaller of the resolved `timeout_seconds` and the seconds left of
  `wall_seconds`; with none left it stops with `budget_exhausted`.
  `turns` counts the requests made and `tool_calls` the calls passed to
  `execute`.
