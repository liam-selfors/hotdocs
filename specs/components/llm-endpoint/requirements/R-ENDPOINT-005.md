# R-ENDPOINT-005

**R-ENDPOINT-005** — A provider credential MUST never appear in a
  `ModelResponse`, a log line, an error message, a URL, or
  `hotdocs.toml`; only the model identifier is ever recorded. A key is
  read only from the process environment variable `hotdocs.toml`'s
  `api_key_env` names, else the provider's standard one
  (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`: each vendor's
  own name, not `VAR_<NAME>`). `claude-cli` reads none itself. The
  credential never reaches any caller (`generator`, `test-author`,
  `spec-completeness-assistant`, `component-gate-runner`'s and
  `capability-scenario-verifier`'s `judge` wiring), so it is structurally
  unable to leak from any of them: a stronger guarantee than "must not
  appear in output".

  For `anthropic`, `openai` and `gemini` a missing key MUST be an `auth`
  `model_call_error` returned without any network call, its message
  naming the missing variable;
  `openai-compatible` and `ollama` send a key only when one is present.
