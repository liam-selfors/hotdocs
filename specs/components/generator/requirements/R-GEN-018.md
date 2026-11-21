# R-GEN-018

**R-GEN-018** — The prompt MUST always
  instruct the candidate that any dynamic runtime load of a
  dependency module — bare `import <module_name>`, a `sys.modules`
  lookup on that bare name, or a path relative to the candidate's own
  `__file__` — MUST instead resolve from the `repo_root` parameter the
  candidate's own function actually received, joined to the module
  path `dependency_usage` gives: `gen/<dep-slug>/`, or a sealed
  dependency's own `source_path` (`D159`), or the same path under the
  tool root (the parent of the nearest `gen` above the module's own
  file) when absent (`D199`); never a stale `sys.modules` entry (`D138`).
