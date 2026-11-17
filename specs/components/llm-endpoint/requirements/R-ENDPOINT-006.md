# R-ENDPOINT-006

**R-ENDPOINT-006** — Every `complete()` call MUST write one record to
  `.hotdocs/calls/` (gitignored, local-only, non-gating —
  `SPEC_GUIDELINES.md` §1, same posture `provenance-tracker`'s
  `.hotdocs/attempts/` already has) — success or failure, before
  returning to the caller. The record MUST carry: a timestamp, `model`,
  `backend`, and either `text`'s presence (not its content — this is a
  transport-level log, not a copy of every prompt/response) or the full
  `model_call_error` object.

  It is caller-agnostic and lower-level than any record a caller keeps
  of its own attempt (`D19`): it answers how many calls went to which
  backend, with what error rate.
