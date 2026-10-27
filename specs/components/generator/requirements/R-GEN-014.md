# R-GEN-014

**R-GEN-014** — A static `sys.path`-relative-to-`__file__` import of
  this component's own dependencies (`cache-manager`, `llm-endpoint`)
  is a valid implementation choice (it's always correct in production,
  since this component's own installed location and the `repo_root`
  it's given always coincide there) **but silently reuses the first
  call's module if `generate` is ever invoked more than once in the
  same process against two *different* `repo_root` values** — exactly
  the shape of a pre-swap-in verification harness staging an untested
  candidate elsewhere while exercising it against real dependencies.
  An implementation that instead resolves dependencies dynamically,
  per call, from the `repo_root` actually passed in (avoiding that
  staleness) MUST register the loaded module in `sys.modules` under
  its load-time name *before* its code runs (`exec_module`) — never
  after, never omitted. Skipping this step is not harmless laziness:
  any dependency module that defines a `dataclass` (both
  `cache-manager` and this component's own `GenerationResult` do) can
  crash during its own class-body evaluation, because `dataclasses`'
  internals look up `sys.modules[cls.__module__]` to resolve the
  class's own annotations — found only once a real self-regeneration
  candidate chose exactly this per-call dynamic-loading technique,
  omitted the registration step, and crashed for real loading
  `cache-manager` (`D41`).
