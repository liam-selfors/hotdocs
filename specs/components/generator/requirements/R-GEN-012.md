# R-GEN-012

**R-GEN-012** — The model call MAY optionally receive `retry_feedback` —
  a bare list of `R-id`s a **caller** supplies as having failed on some
  prior attempt. When present, it MUST be its own distinct context section,
  never merged with the `SpecBundle`'s fields.

  `retry_feedback` MUST contain **only** `R-id`s — never Gherkin text,
  `rationale`, expected/actual values, or any other acceptance-criterion
  content (R-ASSEMBLE-001).

  This component MUST NOT derive `retry_feedback` itself: the list
  comes only from the caller.
