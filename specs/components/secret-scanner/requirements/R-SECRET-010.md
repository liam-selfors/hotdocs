# R-SECRET-010

**R-SECRET-010** — `gate_version(repo_root)` MUST return exactly the
  `gate_version` that `scan(repo_root)` would report under the same
  `VAR-SECRET-PATTERNS-PATH` value — including when the pattern
  database is missing or malformed. It MUST NOT read any file under
  `specs/`, `gen/`, or `verification/`, call `cache-manager`, or write
  anything. This is how a caller learns the scanner's current version
  without running a scan (`D163`).
