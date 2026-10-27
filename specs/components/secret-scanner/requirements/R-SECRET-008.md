# R-SECRET-008

**R-SECRET-008** — The scanner MUST support a separate, lightweight
  invocation mode — scoped only to the files touched by a pending commit or
  push, not the whole corpus — for use as a pre-commit/pre-push hook,
  distinct from the full merge-gate run ("as early as pre-commit/
  pre-push where tooling allows"). This mode uses the same pattern database
  and detection logic, just a narrower file set and no cache-manager
  dependency (a pre-commit hook running before a commit even exists has
  nothing stable to key a cache entry on).
