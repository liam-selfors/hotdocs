# R-RUNENV-007

**R-RUNENV-007** — For a component, `env_for(code_dir)` MUST also return
  `HOTDOCS_SCREENSHOTS`, the absolute path
  `<repo_root>/.hotdocs/screenshots/<slug>`, when `code_dir` resolves to
  `<repo_root>/gen/<slug>` resolved, a criterion run of the code itself,
  and MUST leave it out for any other directory, such as a mutation
  sandbox's copy, and for every `prepare_capability` result. `prepare`
  and `env_for` MUST NOT remove or write anything under
  `.hotdocs/screenshots/`: `provenance-checker` calls `prepare` to read
  environment versions. The plugin's driver fixture MUST take
  pytest's `request` besides `tmp_path`, and at teardown, after the
  session's `close()`, when `HOTDOCS_SCREENSHOTS` is set, copy every
  `*.png` directly under `<tmp_path>/screenshots/` into
  `<HOTDOCS_SCREENSHOTS>/<stem>/`, `<stem>` the test file's name without
  `.py` (`test_ac_ui_013`), first removing that `<stem>/` directory when
  it exists, so it holds only this run's pages, and creating
  directories as needed; a failed
  copy is skipped and never fails the test (`D390`).
