# R-GATE-003

**R-GATE-003** — MUST call `generator` **exactly once** per non-sealed
  miss per invocation — no automatic retry loop (`D3`). If that one call
  does not produce a passing candidate, the component is blocked
  (`R-GATE-004`) for this attempt. That call carries `retry_feedback`
  only when the caller supplied it (`--retry-feedback`, `D86`); this
  component never derives it.
