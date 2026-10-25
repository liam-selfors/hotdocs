# R-GEN-012

**R-GEN-012** — The model call MAY optionally receive `retry_feedback` —
  a bare list of `R-id`s a **caller** supplies as having failed on some
  prior attempt. When present, it MUST be included as its own clearly
  distinguished context section, never merged with or indistinguishable
  from the `SpecBundle`'s own fields — the same clear-separation
  discipline `R-GEN-002` already established for `hint_code`.

  `retry_feedback` MUST contain **only** `R-id`s — never Gherkin text,
  `rationale`, expected/actual values, or any other acceptance-criterion
  content. This boundary is load-bearing, not a style preference: it is
  the entire reason this mechanism doesn't reopen
  `spec-bundle-assembler`'s R-ASSEMBLE-001 exclusion of `acceptance/`
  from what a generation model ever sees. A list of failed `R-id`s
  discloses nothing beyond "a prior attempt didn't satisfy text you
  already have" — the requirements themselves are already in the bundle
  via `requirements/`.

  **Restores what `D31` mistakenly removed along with automatic retry
  (`D33`).** `D31`'s actual point — no *automatic* loop deciding to
  retry on this component's behalf within one merge — never required
  removing the feedback mechanism itself; that was overreach. This
  component MUST NOT be the one deciding *whether* to use
  `retry_feedback` on a given call, and MUST NOT derive it from
  anything on disk itself — that decision, and the R-id list itself,
  come from whoever is invoking this merge/generation (`R-MERGE-022`),
  never computed automatically in between.
