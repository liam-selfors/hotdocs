# R-TOOL-001

**R-TOOL-001** — `run_tool_loop` MUST resolve `model` first. A provider
  of `gemini` or `ollama` MUST raise `ToolUseUnsupported`, naming the
  provider, before any request or process is started. An HTTP provider
  that needs a key and finds none in the environment MUST return at once
  with `stop` `error`, `model_call_error` category `auth`, `turns` `0`
  and no request made.
