# R-GEN-012

**R-GEN-012** — The model call MAY optionally receive `retry_feedback` —
  a bare list of `R-id`s a **caller** supplies as having failed on some
  prior attempt. When present, it MUST be included as its own clearly
  distinguished context section, never merged with or indistinguishable
  from the `SpecBundle`'s own fields — the same clear-separation
  discipline `R-GEN-002` already established for `hint_code`.

  `retry_feedback` MUST contain **only** `R-id`s — never Gherkin text,
  `rationale`, expected/actual values, or any other acceptance-criterion
  content. This boundary is what keeps `acceptance/` out of everything a
  generation model sees (R-ASSEMBLE-001): a list of failed `R-id`s
  discloses nothing beyond "a prior attempt didn't satisfy text you
  already have".

  This component MUST NOT decide whether to use `retry_feedback`, and
  MUST NOT derive it from anything on disk itself: the list comes from
  the caller, a developer's `--retry-feedback` or an attempt loop.
