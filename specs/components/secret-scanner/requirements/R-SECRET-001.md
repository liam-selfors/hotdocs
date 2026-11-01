# R-SECRET-001

**R-SECRET-001** — On a full scan, the scanner MUST check every text
  file under `specs/`, `gen/`, and `verification/` — skipping any
  `__pycache__` directory and any file that does not decode as UTF-8,
  since compiled bytecode and binaries are not where a committed
  secret is written — against a pattern database
  (common API-key/token shapes) and a high-entropy-string heuristic
  (Shannon entropy over a sliding window, flagging a string at or above
  **4.0 bits/char** as entropy-suspicious even with no shape match — a
  threshold that catches random-looking base64/hex-style secrets while
  tolerating ordinary prose and most identifier names, which run
  meaningfully lower). Each pattern-database rule MUST carry a declared
  **`risk_tier`** (`high` / `medium` / `low`) — `high` for a recognizable,
  provider-specific credential shape (e.g. an AWS access-key-ID format, a
  GitHub PAT prefix, a PEM private-key block), `low` for the entropy
  heuristic alone with no specific shape behind it (more prone to false
  positives; a real secret is possible but far less certain from the
  pattern alone). A span a pattern rule matched is never also reported
  by the entropy heuristic: one match per secret, the pattern's.

  **Entropy heuristic, exactly:** each maximal run of
  `[A-Za-z0-9+/=_-]` at least 20 characters long is a candidate; it
  matches if any 20-character window of it has Shannon entropy of at
  least 4.0 bits per character. The match is reported with `rule_id`
  `"entropy-heuristic"` and `risk_tier` `"low"`.

  **Resolves the pattern-database question:** the shape database MUST be
  sourced from a maintained, continuously-updated external reference set
  (the kind of curated rule set tools like `gitleaks`/`detect-secrets`
  already maintain and update as new provider key formats emerge), never
  hand-rolled and frozen into this spec. New leaked-credential shapes
  (a new cloud vendor, a new token prefix convention) appear regularly; a
  one-time, spec-frozen list would silently stop catching real patterns
  without ever reporting that it had gone stale — the same reasoning
  `license-scanner`'s reference-corpus sourcing follows (`R-LICENSE-001`).

  **Where the pattern database lives:** `VAR-SECRET-PATTERNS-PATH`,
  never `.hotdocs/` — mirroring `license-scanner`'s own
  `VAR-LICENSE-CORPUS-PATH` fix exactly (`D53`; see `D51` for why
  `.hotdocs/` can never be the real answer for input that determines
  a gate's pass/fail decision). A missing or unreachable database MUST
  still produce a real, recorded result — the entropy heuristic alone
  needs no external database and still runs regardless.
