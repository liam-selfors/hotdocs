# R-ENDPOINT-001

**R-ENDPOINT-001** — MUST expose exactly one entry point,
  `complete(prompt, model, **params) -> ModelResponse`, given an explicit
  model identifier as a required parameter — never hardcoded to a
  canonical pin, never defaulted to a specific vendor. A caller supplies
  the prompt text and which model to use; this component owns everything
  between that call and a response coming back.
