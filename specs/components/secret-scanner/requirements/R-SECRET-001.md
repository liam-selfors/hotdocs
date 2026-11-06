# R-SECRET-001

**R-SECRET-001** — A full scan MUST check every text file under
  `repo_root`, with no per-directory or per-component exceptions, using
  the `detect-secrets` library (`interface/library.md`), never a
  detector of its own (`D168`). Only these are skipped: any directory
  named `.git`, `__pycache__`, `.pytest_cache`, `.venv`, `.hotdocs`, or
  `node_modules`, and any file that does not decode as UTF-8.

  The scan runs every plugin the installed library provides except
  `KeywordDetector` and `IPPublicDetector`, each with its own default
  settings, and with **no** `detect-secrets` filters: nothing may
  suppress a finding except `R-SECRET-012`'s allowlist.

  Each finding is one match. `rule_id` is the library's secret type
  string unchanged (e.g. `"AWS Access Key"`). `risk_tier` is `"low"`
  for `"Base64 High Entropy String"` and `"Hex High Entropy String"`
  and `"high"` for every other type. A match carries `file`, `line`,
  `rule_id`, and `risk_tier`, never the secret itself or its hash.
  `matches` is sorted by `file`, then `line`, then `rule_id`.
