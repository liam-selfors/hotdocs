# Agentic Generator — Non-Functional Constraints

- **The bundle is the whole world.** Nothing from the repository but
  `render_prompt_sections`' text enters the sandbox, and no tool reads
  outside it.
- **Fails closed.** Without an OS sandbox, code is not run unless the
  caller explicitly allows it, and the result says which happened.
- **No credential reaches model-run code.** Its environment is exactly
  `specs/architecture/agent-sandbox.md`'s.
- **Leaves nothing behind.** The sandbox and its profile file are
  removed before `generate_agentic` returns, whatever the outcome.
