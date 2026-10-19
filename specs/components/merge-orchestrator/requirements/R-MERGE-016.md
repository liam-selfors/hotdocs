# R-MERGE-016

**R-MERGE-016** — `k` (best-of-k's total attempt count, R-MERGE-005)
  defaults to **2**: one initial attempt, and — only if that fails — one
  retry informed by `retry_feedback`. A component MAY override this
  default via its own `component.md` frontmatter's `best_of_k` field (an
  integer, 2–4 inclusive); `merge-orchestrator` MUST read that field when
  present and MUST fall back to 2 when absent.

  The default of 2, not a larger number, reflects what diagnostic-guided
  retry (R-GEN-010) actually changes: when each retry is informed by what
  specifically failed last time rather than being a blind re-roll, most of
  the value of "try again" is captured in a single informed retry — a
  third or fourth blind-ish attempt buys much less than the first informed
  one did. Raising `best_of_k` above 2 for a specific component is for
  cases where even informed retries are expected to need more than one
  additional pass (e.g. a component whose requirements are unusually
  numerous or interdependent) — an explicit, visible, per-component
  opt-in, not a corpus-wide default tuned for the hard case.
