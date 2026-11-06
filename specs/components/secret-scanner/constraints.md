# Secret Scanner — Non-Functional Constraints

- **Determinism (full-scan form).** The same repository content,
  allowlist, and `detect-secrets` version MUST give the same result,
  which cache-key correctness requires (`D30`).
- **No model calls**; no network but the webhook.
- **Never silent.** A clean result is recorded as rigorously as a
  flagged one (`R-SECRET-003`/`009`), and every suppressed finding is
  listed.
- **Fail closed:** doubt about the allowlist reports more findings.
- **Precommit** scans only the given files.
- **Matches never carry the secret or its hash;** hashes appear only in
  the allowlist and `propose`'s output.
