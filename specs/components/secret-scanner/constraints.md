# Secret Scanner — Non-Functional Constraints

- **Determinism (full-scan form).** The same repository content,
  allowlist, and `detect-secrets` version MUST give the same result,
  which cache-key correctness requires (`D30`).
- **No model calls**, and no network but the optional webhook.
- **Never silent.** A clean result is recorded as rigorously as a
  flagged one, history is never collapsed to the final state
  (`R-SECRET-003`/`009`), and every suppressed finding is listed.
- **Fail closed.** Any doubt about the allowlist reports more findings,
  never fewer.
- **Precommit latency.** `precommit` scans only the given files.
- **Matches never carry the secret or its hash.** Hashes appear only in
  the allowlist and `propose`'s output, which a person reviews.
