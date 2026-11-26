# LLM Tool Endpoint — Non-Functional Constraints

- **Bounded.** Every loop ends within its wall-clock budget plus one
  request timeout; every HTTP request has a timeout.
- **Credentials stay out of results.** No key, header or vendor error
  text appears in `ToolLoopResult`, its transcript or any message.
- **No user context leaks into a `claude-cli` call.** The command never
  loads the user's CLAUDE.md, AGENTS.md, skills, hooks or memory, and
  exposes no tool but the caller's.
