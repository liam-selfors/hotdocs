# R-AUTHOR-022

**R-AUTHOR-022** — The prompt MUST instruct that a test MUST NEVER
  assert a fake was used by reaching into `sys.modules` under a
  guessed key — real loaders key dynamically (often `repo_root`- or
  hash-qualified, `R-AUTHOR-010`), so any guess is unreliable. To
  confirm a fake ran, its own code MUST record its invocation to a
  **file** (`R-AUTHOR-024`), never an in-process list — the test
  can't reliably re-locate the module object that wrote to it either.

  Found at `D123`: a guessed `sys.modules["real_name"]` assertion
  failed once the loader (correctly) keyed under something else.
