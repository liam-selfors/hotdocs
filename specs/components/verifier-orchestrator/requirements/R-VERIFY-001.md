# R-VERIFY-001

**R-VERIFY-001** — For every `compiled`-kind criterion, this component
  MUST invoke `criterion-compiler` to produce test scaffolding, execute
  it against `gen/<component>/`, and record a pass/fail per criterion.

  Every test run's `PYTHONPATH` MUST be exactly the directory of the
  code being verified (`gen/<component>/`, or the mutation copy) then
  the `asset_runner` plugin's directory, never a broader ancestor such as `gen/`, where
  `import <module_name>` (`R-COMPILE-013`) resolves to an empty
  namespace package.
