# R-AUTHOR-022

**R-AUTHOR-022** — The prompt MUST instruct that a test MUST NEVER
  assert a fake was used by reaching into `sys.modules` under a
  guessed key — real loaders key dynamically (often `repo_root`- or
  hash-qualified, `R-AUTHOR-010`), so any guess is unreliable. To
  confirm a fake ran, its own code MUST record its invocation and the
  test MUST assert against that record instead.

  Found twice at different seeds, same symptom (`D123`): a redundant
  `sys.modules["real_name"]` assertion failed once the loader
  (correctly) keyed under something else.
