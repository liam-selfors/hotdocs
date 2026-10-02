---
id: comp-cache-manager-constraints
title: Cache Manager — Non-Functional Constraints
status: draft
owners: [pipeline-team]
---

# Cache Manager — Non-Functional Constraints

- **Fail closed to "miss," never to a crash.** Per R-CACHE-004 — this is the
  same "the tool must keep working" principle D10 established for model
  availability, applied here to a different subsystem (not a new principle;
  flagged as such rather than silently treated as novel).
- **Never return a stale or wrong-version result.** Per R-CACHE-005 — a
  false cache hit is strictly worse than a miss (a miss just costs
  recomputation; a false hit serves an incorrect result as if it were
  verified).
- **Performance.** `get`/`put` MUST add negligible latency relative to the
  gate work they're short-circuiting — a slow cache defeats D13's purpose.
- **No model calls.** Pure store logic, same trust tier as `spec-linter` and
  `impact-analyzer`.
