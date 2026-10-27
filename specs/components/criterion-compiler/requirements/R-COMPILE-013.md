# R-COMPILE-013

**R-COMPILE-013** — Emitted test code that references the target
  component's own functions or types (any `When ... is invoked` or
  `Given a <fixture> is a <Type>` step bound against a resolved
  `InterfaceSurface`) MUST import the target module by its
  `InterfaceSurface.module_name` and qualify every such reference with
  it (`<module_name>.<name>`) — never a bare, unqualified name relying
  on a caller to have pre-populated globals (`D62`).

  A caller that *executes* the emitted file (any `compiled`-kind
  dispatch, e.g. `verifier-orchestrator`'s `R-VERIFY-001`) MUST run it
  with its import search path (`PYTHONPATH` for `pytest`) scoped to the
  specific directory containing `gen/<component>/<module_name>.py` —
  `gen/<component>/` itself, not a broader ancestor such as `gen/`.
  Scoping any broader resolves `import <module_name>` as an empty
  implicit namespace package rather than the real module, since
  `gen/<component>/` has no `__init__.py` (R-COMPILE-006 writes
  compiled *test* output under `verification/`, but the target code
  under test lives under `gen/<component>/` per the generator's own
  output layout, R-GEN-015).
