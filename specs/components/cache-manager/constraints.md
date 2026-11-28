# Cache Manager — Non-Functional Constraints

- **Fail closed to "miss," never to a crash.** Per R-CACHE-004.
- **Never return a stale or wrong-version result.** Per R-CACHE-005 — a
  false hit is worse than a miss.
- **Performance.** `get`/`put` MUST add negligible latency relative to the
  gate work they're short-circuiting.
- **No model calls.** Pure store logic.
