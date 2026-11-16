# Provenance Writer — Non-Functional Constraints

- **Never invents data.** If a required input is missing, this component
  MUST fail loudly (exit `1`) rather than write a manifest with a guessed
  or default value in that field — a provenance manifest with a fabricated
  field is worse than no manifest at all, since it would be trusted as
  evidence during incident debugging.
- **Determinism.** Given the same `ProvenanceInputs`, the written manifest
  MUST be byte-identical across runs (field ordering included), so it
  participates correctly in any future tooling that diffs or hashes
  provenance manifests themselves.
- **No network access, no model calls.** Pure aggregation and file writing.
