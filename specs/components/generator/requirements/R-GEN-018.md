# R-GEN-018

**R-GEN-018** — Regardless of `depends_on`, the prompt MUST always
  instruct the candidate that any dynamic runtime load of a
  dependency module — bare `import <module_name>`, a `sys.modules`
  lookup on that bare name, or a path relative to the candidate's own
  `__file__` — MUST instead resolve strictly from the `repo_root`
  parameter the candidate's own function actually received:
  `<repo_root>/gen/<dep-slug>/<module_name>.py` (flat) or
  `<repo_root>/gen/<dep-slug>/<module_name>/__init__.py` (package),
  never a cached `sys.modules` entry a different `repo_root`'s earlier
  call may have left behind. Cross-cutting, always-included
  scaffolding like `R-GEN-015`, outside `R-GEN-001`'s boundary.

  Found (`D138`) after the identical defect recurred independently
  across `R-TRACK-011`, `R-VERIFY-013`, and `R-DRIFT-004`. Making it
  universal here closes the whole class at once.
