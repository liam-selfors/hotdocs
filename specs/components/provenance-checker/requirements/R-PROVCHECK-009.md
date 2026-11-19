# R-PROVCHECK-009

**R-PROVCHECK-009** — The current assets value of a component MUST be
  computed as `verifier-orchestrator` records `VerificationReport.assets`
  (`specs/architecture/asset-kinds.md`, Provenance): one entry per
  declaration in `<repo_root>/specs/components/<slug>/component.md`
  frontmatter `assets`, in order, with `definition_sha256` from
  `<repo_root>/specs/architecture/asset-kind-<kind>.md` and
  `adapter_sha256` from the adapter Lookup finds (each `null` when absent),
  `versions` and `lockfile_sha256` from `provision(repo_root)`, called
  once per distinct kind (`{}` and `null` with no adapter). A missing
  `component.md` or `assets` key means `[]`. `current_provenance_key`
  returns it as `assets`. `check_provenance` computes it itself, only
  once `spec_bundle_hash` and `gate_versions` match, and MUST miss when
  a kind lacks an adapter (reason `unknown asset kind:
  <kind>`), when `provision` reports `ok` false (reason: its `reason`,
  verbatim), or when the manifest's `assets` differs from it (reason
  `assets differ`). A manifest with no `assets` field, or `null`,
  compares as `[]`, so it still hits only for a component declaring no
  assets (`D343`).
