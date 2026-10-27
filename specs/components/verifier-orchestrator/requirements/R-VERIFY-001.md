# R-VERIFY-001

**R-VERIFY-001** — For every `compiled`-kind criterion in a component's
  `acceptance/` directory, this component MUST invoke `criterion-compiler`
  to produce test scaffolding, execute it against `gen/<component>/`, and
  record a pass/fail per criterion.

  Executing that scaffolding MUST scope the import search path
  (`PYTHONPATH` for `pytest`) to `gen/<component>/` itself, never a
  broader ancestor such as `gen/` — `criterion-compiler`'s emitted
  `import <module_name>` (`R-COMPILE-013`) only resolves to the real
  module at that specific scope; any broader scope resolves it as an
  empty implicit namespace package instead, since `gen/<component>/`
  has no `__init__.py`. The same scoping applies to any sandboxed copy
  of `gen/<component>/` used for mutation testing (R-VERIFY-006).
