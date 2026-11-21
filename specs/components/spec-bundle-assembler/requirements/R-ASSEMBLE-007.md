# R-ASSEMBLE-007

**R-ASSEMBLE-007** — `spec_bundle_hash` MUST be `"sha256:"` plus the
  SHA-256 hex digest of one byte stream built from the files the bundle
  reads, so every correct implementation computes the same value. The
  stream is the mode (`cold` or `hint`) and a NUL byte, then, for each
  path below in sorted order without duplicates, the repo-relative POSIX
  path in UTF-8, a NUL byte, the file's raw bytes, and a NUL byte:

  - the target's `component.md`, `constraints.md`, and every `.md` file
    under its `requirements/` and `interface/`;
  - each document `R-ASSEMBLE-014` appends;
  - each asset-kind adapter `R-ASSEMBLE-016` loads, under the path
    `gen/kind-<kind>/kind_<module>.py` whichever root it was read from;
  - for each `depends_on` component, its `component.md`, every `.md` file
    under its `interface/`, and every file under its code directory
    (`source_path` when sealed, else `gen/<slug>/`);
  - each type file `R-ASSEMBLE-013` appends, each `uses_var` declaration,
    and `specs/glossary.md`;
  - in `hint` mode, every file under `gen/<target>/`.

  A code directory never contributes a file whose name starts with `.`
  or anything under `__pycache__`, so writing a manifest there changes no
  hash. A missing file or directory contributes nothing.
