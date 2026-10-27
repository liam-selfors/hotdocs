# R-ENDPOINT-005

**R-ENDPOINT-005** — A backend credential (`VAR-ANTHROPIC-API-KEY` in v1)
  MUST never appear in a `ModelResponse`, a log line, or an error
  message — only the model identifier actually used is ever recorded.
  Centralizes the guard `R-AUTHOR-008` previously stated for
  `test-author` alone; now that the credential never reaches any caller
  (`generator`, `test-author`, `spec-completeness-assistant`,
  `component-gate-runner`'s and `capability-scenario-verifier`'s own
  `judge` wiring) at all, it is structurally
  unable to leak from any of them — a strictly stronger guarantee than
  "must not appear in output," which only ever covered a component that
  held the credential in the first place.
