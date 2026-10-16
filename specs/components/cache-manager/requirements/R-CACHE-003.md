# R-CACHE-003

**R-CACHE-003** — `put` MUST uphold the consistency guarantee declared in
  `interface/guarantees/G-CACHE-001.md` — concurrent calls (from parallel
  gate runs, per D13's "parallelize independent gates") MUST NOT corrupt
  either entry, and `put` MUST NOT silently merge or partially overwrite a
  stored result. (Retrofitted during D16 to reference the guarantee file
  directly rather than restate its content — the same "generated code
  MUST match `interface/` exactly" pattern `verifier-orchestrator`'s
  R-VERIFY-004 already established for type contracts, applied here to a
  behavioral one.)
