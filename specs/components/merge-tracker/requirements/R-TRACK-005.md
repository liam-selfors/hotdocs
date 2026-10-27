# R-TRACK-005

**R-TRACK-005** — This component MUST NOT make this component's own
  success a precondition for the merge's own success or failure, and
  `merge-orchestrator` MUST NOT block or alter a merge's outcome based on
  whether this component's write succeeds — `write_tracking_record` and
  `write_attempt_record` (`R-TRACK-007`, `D19`) alike. A merge that
  passes every real gate but fails to write either kind of record is
  still a passed merge.

  This is the normative form of `component.md`'s open question about
  best-effort behavior — resolved to the extent that it does not gate the
  merge; a write failure's own visibility (how loudly it should surface)
  is left open, not silently decided by making this a hard dependency of
  the merge outcome.
