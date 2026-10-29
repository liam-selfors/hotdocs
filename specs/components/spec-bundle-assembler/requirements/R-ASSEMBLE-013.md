# R-ASSEMBLE-013

**R-ASSEMBLE-013** — `dependency_interfaces`' entry for each
  dependency MUST also resolve, one level deep, any data type that
  dependency's own `interface/` content names but does not itself
  own. For each bare `TypeName` token appearing in a dependency's
  rendered interface text, search the whole corpus (not only the
  target's own `depends_on`) for exactly one component whose
  `interface/data/<TypeName>.md` exists; if found, append that type's
  own content to the same dependency's entry, under a clearly labeled
  heading naming the type and its real owning component — never
  merged in as if the dependency owned it. Ambiguous (more than one
  owner) or unresolved (no owner) names are skipped silently — never
  a guess. Expansion is one level only: a referenced type's own
  further references are never followed.

  **Found only once a transitive type reference was the actual,
  confirmed blocker for a real component's own bootstrap** (`D114`):
  `provenance-checker`'s own `ProvenanceCheckResult.verification_report`
  names `VerificationReport` only as an opaque placeholder
  (`{"...": "a VerificationReport"}`) since `provenance-checker`
  itself correctly never depends on `verifier-orchestrator`, the
  type's real owner — leaving a `provenance-tracker` test-authoring
  no way to construct a realistic fake `verification_report` at all.
  This was flagged as a known, deferred limitation twice (`D110`,
  `D112`) before actually blocking a real bootstrap for the first
  time.
