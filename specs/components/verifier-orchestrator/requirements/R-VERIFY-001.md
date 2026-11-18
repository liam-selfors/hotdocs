# R-VERIFY-001

**R-VERIFY-001** — For every `compiled`-kind criterion in a component's
  `acceptance/` directory, this component MUST invoke `criterion-compiler`
  to produce test scaffolding, execute it against `gen/<component>/`, and
  record a pass/fail per criterion.

  Executing that scaffolding MUST scope the import search path
  (`PYTHONPATH` for `pytest`) to `gen/<component>/` itself, never a
  broader ancestor such as `gen/`, where `criterion-compiler`'s
  `import <module_name>` (`R-COMPILE-013`) resolves to an empty
  namespace package.
