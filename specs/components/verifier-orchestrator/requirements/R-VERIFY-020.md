# R-VERIFY-020

**R-VERIFY-020** — For a component's assets, the implicit `python` one
  first, then those it declares (`specs/architecture/asset-kinds.md`,
  `D343`, `D344`), this component MUST:

  1. find each kind's adapter by asset-kinds.md's Lookup and give
     every test run `specs/architecture/verifier-fixtures.md`'s
     `asset_runner` plugin.
  2. before any criterion runs, call `provision(repo_root)` once per
     distinct kind with an adapter. When, in that order, a kind has no
     adapter or its report has `ok` false, every
     `generated-test` and `compiled` criterion is `fail` with `failure_origin`
     `"environment"` and `failure_detail.message`
     `unknown asset kind: <kind>` or the report's `reason` for the first
     such kind, and none is
     authored, probed or run; `mutation_score` and `mutation_error` are
     null.
  3. run pytest, for criteria and mutation alike, under the `python`
     report's `interpreter`.
  4. report `assets` as asset-kinds.md's Provenance bullet states; a
     kind with no adapter has `adapter_sha256` null, `versions` `{}`
     and `lockfile_sha256` null, and a kind the repository does not
     define `definition_sha256` null.
