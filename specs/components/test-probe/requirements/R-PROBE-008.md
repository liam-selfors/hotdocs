# R-PROBE-008

**R-PROBE-008** — `probe` MUST take a keyword argument
  `interpreter: str | None = None`, the Python the component's tests run
  under (`D344`), `None` meaning `sys.executable`. The stub run
  (`R-PROBE-005`) MUST be `<interpreter> -m pytest ...`, and an import's
  first dotted part (`R-PROBE-003`) is resolved with
  `importlib.util.find_spec` under that interpreter: in the probing
  process for `None`, else in one subprocess of `interpreter`.
