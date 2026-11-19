# R-PROVCHECK-005

**R-PROVCHECK-005** — `current_provenance_key(component_id, repo_root)`
  MUST return a `ProvenanceKey` whose `spec_bundle_hash` is exactly
  `spec-bundle-assembler`'s cold-mode bundle hash for that component,
  and whose `gate_versions` maps exactly `compiler`, `generated_test`,
  `verifier`, `license_scanner`, `secret_scanner` and `generator` to the
  values `interface/library.md` names, unchanged but for `generator`,
  which is `generator`'s `GATE_VERSION`, `+`, and its `PROMPT_VERSION`,
  and whose `assets` is `R-PROVCHECK-009`'s. It MUST NOT run any scan,
  generation, or verification, and MUST NOT write anything. A
  dependency that cannot be loaded, or an exception from
  `assemble`, propagates to the caller unchanged — never a guessed or
  empty key, which would make every check a miss without saying why
  (`D163`).
