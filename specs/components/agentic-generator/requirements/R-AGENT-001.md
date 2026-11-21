# R-AGENT-001

**R-AGENT-001** — `generate_agentic` MUST first call `generator`'s
  `check_write_allowed(bundle, repo_root)`. A reason makes it return a
  `GenerationResult` with `refused` that reason, `mode` `"agentic"`,
  `turns` `0` and `tool_calls` `0`, without creating a sandbox or calling
  `run_tool_loop`. It MUST then call `generator`'s
  `check_asset_environment(bundle["component_id"], repo_root)`; a
  category makes it return, likewise, `model_call_error`
  `{"category": <that>, "message": <the messages joined by "\n">}`
  (`D343`).
