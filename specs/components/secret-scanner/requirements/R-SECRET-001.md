# R-SECRET-001

**R-SECRET-001** — On a full scan, the scanner MUST check every file
  under `specs/`, `gen/`, and `verification/` against a pattern database
  (common API-key/token shapes) and a high-entropy-string heuristic. Each
  pattern-database rule MUST carry a declared **`risk_tier`** (`high` /
  `medium` / `low`) — `high` for a recognizable, provider-specific
  credential shape (e.g. an AWS access-key-ID format, a GitHub PAT prefix, a
  PEM private-key block), `low` for a generic high-entropy-string heuristic
  with no specific shape behind it (more prone to false positives; a real
  secret is possible but far less certain from the pattern alone).
