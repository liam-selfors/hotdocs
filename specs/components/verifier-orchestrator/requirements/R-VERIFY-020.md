# R-VERIFY-020

**R-VERIFY-020** — For the assets a component declares
  (`specs/architecture/asset-kinds.md`, `D343`), this component MUST:

  1. find each kind's definition and adapter by asset-kinds.md's Lookup,
     with `verify`'s tool root as `<tool_root>`, and give every test
     run the `asset_runner` plugin `specs/architecture/verifier-fixtures.md`
     describes.
  2. before any criterion runs, call `provision(repo_root)` once per
     distinct declared kind with an adapter. When, in declaration
     order, a kind has no adapter or its report has `ok` false, every
     `generated-test` criterion is `fail` with `failure_origin`
     `"environment"` and `failure_detail.message`
     `unknown asset kind: <kind>` or the report's `reason` for the first
     such kind, and none is
     authored, probed or run; `mutation_score` and `mutation_error` are
     null.
  3. report `assets` as asset-kinds.md's Provenance bullet states; a
     kind with no adapter has `adapter_sha256` null, `versions` `{}`
     and `lockfile_sha256` null, and a kind with no definition
     `definition_sha256` null.
