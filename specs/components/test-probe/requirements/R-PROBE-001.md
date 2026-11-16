# R-PROBE-001

**R-PROBE-001** — `probe` MUST first `ast.parse` the source. A
  `SyntaxError` gives exactly one finding, `syntax_error` with the
  error's line, and `probe` returns at once: no other check and no stub
  run, `tests_run` and `tests_reached` both `0`.
