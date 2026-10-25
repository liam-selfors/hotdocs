# R-MERGE-016

**R-MERGE-016** — `k` (best-of-k's total attempt count, R-MERGE-005)
  defaults to **2**: one initial attempt, and — only if that fails — one
  retry informed by `retry_feedback`. A component MAY override this
  default via its own `component.md` frontmatter's `best_of_k` field (an
  integer, 2–4 inclusive); `merge-orchestrator` MUST read that field when
  present and MUST fall back to 2 when absent.

  Rationale for 2 as the default, not a larger number: `specs/decisions/
  D17.md`. Raising `best_of_k` for a specific component is for cases
  where even an informed retry is expected to need more than one
  additional pass — an explicit, visible, per-component opt-in, not a
  corpus-wide default tuned for the hard case.
