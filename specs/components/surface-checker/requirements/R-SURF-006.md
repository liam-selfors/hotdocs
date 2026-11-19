# R-SURF-006

**R-SURF-006** — Before any other check, `check_surface` MUST call the
  `python` adapter's `provision(repo_root)`, the adapter found by
  `specs/architecture/asset-kinds.md`'s Lookup, in a subprocess with a
  600-second timeout (`D344`). Its `interpreter` is the interpreter of
  every subprocess that imports the candidate or a dependency
  (`R-SURF-001` to `R-SURF-003`). When there is no adapter, `ok` is
  false, the subprocess fails or it times out, the findings are exactly
  one `environment` finding, message `unknown asset kind: python`, the
  `reason`, `python environment: <last non-empty stderr line>` or
  `python environment: timed out`, and no other check runs.
