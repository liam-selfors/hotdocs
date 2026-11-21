# LLM Tool Endpoint — Non-Functional Constraints

- **No retries.** A failed request ends the loop with a
  `model_call_error`, exactly once, as `llm-endpoint` does.
- **Bounded.** Every loop ends within its wall-clock budget plus one
  request timeout; every HTTP request has a timeout.
- **Credentials stay out of results.** No key, header or vendor error
  text appears in `ToolLoopResult`, its transcript or any message.
- **No user context leaks into a `claude-cli` call.** The command never
  loads the user's CLAUDE.md, AGENTS.md, skills, hooks or memory, and
  exposes no tool but the caller's.
- **Leaves nothing behind.** Temporary files and the socket live in one
  temporary directory removed before `run_tool_loop` returns.
