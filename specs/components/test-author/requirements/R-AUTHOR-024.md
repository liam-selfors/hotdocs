# R-AUTHOR-024

**R-AUTHOR-024** — Confirming a dynamically-loaded fake was invoked
  MUST use a file-based invocation log — the fake appends its
  invocation record to a file under a path the test controls — never
  an in-process, module-level list read via any `sys.modules` lookup.
  A correct candidate may key `sys.modules` dynamically (`R-GEN-018`),
  so the key is never predictable from the test's side; only a file
  survives regardless of which module object the candidate used.

  Found (`D144`): an earlier fix (`D143`) instructed reading
  `sys.modules[module_name]` under the bare dependency name — the
  guessed-key failure `R-AUTHOR-022` already forbade.
