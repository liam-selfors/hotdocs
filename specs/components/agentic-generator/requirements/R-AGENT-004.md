# R-AGENT-004

**R-AGENT-004** — `check_import` and `run_scratch_tests` MUST run their
  commands exactly as the Running code section says: the environment,
  limits and timeout, and the OS sandbox for the platform. When no OS
  sandbox is available they MUST refuse unless `allow_unisolated_exec`
  is true. The result's `isolation` is the level used by the last such
  run, or, when none ran, the level one would have used.
