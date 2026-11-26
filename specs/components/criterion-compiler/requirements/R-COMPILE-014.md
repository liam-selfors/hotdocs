# R-COMPILE-014

**R-COMPILE-014** — The module MUST work when loaded by path alone, as
  every dependent loads it (`D199`, `D375`): `criterion_compiler.py`
  (or the package `criterion_compiler/`) copied into any directory and
  imported from there, with that directory as its only addition to
  `sys.path`, exposes `compile` and `compile_criterion`, and its
  `__file__` lies in that directory. It imports no other `hotdocs`
  component at module level.
