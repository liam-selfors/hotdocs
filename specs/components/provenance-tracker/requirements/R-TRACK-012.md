# R-TRACK-012

**R-TRACK-012** — `check_readiness` MUST read every field of a value
  a dependency returns (`provenance-checker`'s `ProvenanceCheckResult`,
  `impact-analyzer`'s `BlastRadiusReport`, and each entry of its
  `impacted` list, `capability-scenario-verifier`'s own result) using
  dual dict-or-attribute access, never a bare `.attr` access alone —
  this corpus's duck-typing convention (`D94`) means any dependency
  may return either shape, and a dependency is never required to
  match whichever shape happened to be convenient for this
  component's own guess.

  **Found only once test-authoring finally had this component's real
  dependency shapes available to build an accurate fake against**
  (`D121`, downstream of `D119`'s fix): `check_readiness`'s own code
  reads `result.hit` and `entry.component_id` via bare attribute
  access; a dict-shaped fake (matching the real, documented shape
  exactly, for the first time) crashed outright. Previously masked
  entirely — every earlier fake guessed the wrong shape for an
  unrelated reason first, so this never had a chance to run.
