# R-AGENT-006

**R-AGENT-006** — When `finish` was never called, nothing MUST be
  written and `files` MUST be empty. The loop's `stop` decides `model_call_error`: `error`
  passes on the loop's own `model_call_error` unchanged; `budget_exhausted`
  gives category `agent_budget_exhausted`; any other stop gives
  `agent_unfinished`, each with a non-empty `message` naming the stop.
