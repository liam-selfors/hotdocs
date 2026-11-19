# R-GEN-014

**R-GEN-014** — An implementation that loads its dependencies
  (`cache-manager`, `llm-endpoint`) dynamically, per call, from the
  `repo_root` passed in MUST register each loaded module in
  `sys.modules` under its load-time name *before* its code runs
  (`exec_module`) — never after, never omitted — since a module
  defining a `dataclass` looks itself up there while its class body
  runs (`D41`). A static `sys.path` import relative to `__file__` is
  also allowed.
