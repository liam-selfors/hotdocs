# R-MERGE-008

**R-MERGE-008** — MUST invoke `license-scanner` and `secret-scanner`
  unconditionally for every impacted component — never toggle-gated
  (D7/D12). This call and R-MERGE-004's generation call MAY run in
  parallel with each other per component (D13) — they have no sequential
  dependency on each other given the same inputs.
