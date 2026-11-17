# R-PROBE-003

**R-PROBE-003** — For each `import X` and `from X import ...` statement
  anywhere in the source, `probe` MUST take `X`'s first dotted part and
  report one `unknown_import` finding, with the statement's line and the
  message `cannot import '<part>'`, when that part is no name of `module_name`,
  is not in `sys.stdlib_module_names`, and
  `importlib.util.find_spec(<part>)` returns `None`. A relative import, or
  an import inside a `try` block that has an `except` clause naming
  `ImportError` or `ModuleNotFoundError`, is never reported.
