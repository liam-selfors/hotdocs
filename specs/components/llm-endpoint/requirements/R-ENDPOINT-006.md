# R-ENDPOINT-006

**R-ENDPOINT-006** — Every `complete()` call MUST write one record to
  `.hotdocs/calls/` (gitignored, local-only, non-gating —
  `SPEC_GUIDELINES.md` §1, same posture `merge-tracker`'s
  `.hotdocs/tracking/` already has) — success or failure, before
  returning to the caller. The record MUST carry: a timestamp, `model`,
  `backend`, and either `text`'s presence (not its content — this is a
  transport-level log, not a copy of every prompt/response) or the full
  `model_call_error` object.

  This is deliberately a different, lower-level record than anything a
  caller (`generator`, `test-author`, `merge-orchestrator`'s `judge`
  wiring) separately persists about its own attempt — `D19`. This one
  is caller-agnostic: it answers "how many calls, to which backend, with
  what error rate" across the whole pipeline, independent of which
  component's semantics any individual call served. Writing it here,
  once, is what `D18` already made this component the right place for —
  every model call already passes through here regardless of caller.
