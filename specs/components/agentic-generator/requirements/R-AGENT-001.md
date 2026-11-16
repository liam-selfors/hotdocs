# R-AGENT-001

**R-AGENT-001** — `generate_agentic` MUST first call `generator`'s
  `check_write_allowed(bundle, repo_root)`. A reason makes it return a
  `GenerationResult` with `refused` that reason, `mode` `"agentic"`,
  `turns` `0` and `tool_calls` `0`, without creating a sandbox or calling
  `run_tool_loop`.
