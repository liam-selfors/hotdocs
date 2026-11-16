# R-TOOL-007

**R-TOOL-007** — For `claude-cli`, `run_tool_loop` MUST, in one fresh
  temporary directory: write `tools` to `tools.json`; listen on a Unix
  socket `mcp.sock`; write `mcp.json` as
  `{"mcpServers": {"hotdocs": {"command": <sys.executable>, "args":
  [<this module's file>, "--mcp-serve", <socket path>, <tools.json path>]}}}`;
  and run `claude_command` with the wire-format document's arguments, one
  `--allowedTools` value `mcp__hotdocs__<name>` per tool, and
  `--max-turns <max_turns>`, the prompt on stdin, in that directory, killed
  after `wall_seconds`. A thread answers each socket connection's request
  lines `{"name", "arguments"}` with `{"text", "is_error"}` lines, applying
  `R-TOOL-004` and `R-TOOL-005`'s tool-call cap; a call past the cap is
  answered `tool-call budget exhausted` as an error and sets `stop`
  `budget_exhausted`. The last stdout line whose JSON `type` is `result`
  gives `text` from `result` and `turns` from `num_turns`; a `subtype` of
  `error_max_turns`, or a killed process, gives `budget_exhausted`
  whatever the exit code; a
  non-zero exit or no result line gives `error`, category `network`,
  unless `budget_exhausted` is already set. Otherwise, an exit of `0`
  gives `end_turn`, or `budget_exhausted` when a call was past the cap.
  The loop never waits for a socket connection: it returns once the
  process has exited or been killed, after closing the socket and
  removing the directory.
