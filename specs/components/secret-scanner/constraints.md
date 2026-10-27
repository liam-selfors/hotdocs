# Secret Scanner — Non-Functional Constraints

- **Determinism (full-scan form).** Same corpus content and pattern
  database version MUST always produce the same result — required for
  cache-key correctness (`D30`).
- **No model calls.** Pure pattern/entropy matching.
- **Never silent.** Per R-SECRET-003/009 — a clean result is recorded with
  the same rigor as a flagged one, and history is never collapsed to just
  the final state.
- **Precommit-mode latency.** The `precommit` invocation MUST be fast enough
  not to meaningfully slow down a local `git commit`/`git push` — it scans
  only the given files, not the whole corpus, specifically to keep this
  bounded regardless of overall repo size.
- **Matches never echo the full matched string.** A reported match MUST
  redact/truncate the matched text (e.g. first/last few characters only) —
  the scan result itself must not become a second place a real secret is
  exposed in plain text.
