# R-ENDPOINT-006

**R-ENDPOINT-006** — Every `complete()` call MUST write one record to
  `.hotdocs/calls/` (gitignored, local-only, non-gating —
  `SPEC_GUIDELINES.md` §1) — success or failure, before
  returning to the caller. The record MUST carry: a timestamp, `model`,
  `backend`, and either `text`'s presence (not its content — this is a
  transport-level log, not a copy of every prompt/response) or the full
  `model_call_error` object.
