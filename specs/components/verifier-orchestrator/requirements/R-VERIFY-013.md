# R-VERIFY-013

**R-VERIFY-013** — Every dynamically loaded module (the component under
  test, `criterion-compiler`, `spec-bundle-assembler`, any other
  dependency, an asset adapter) MUST be cached, if at all, keyed by
  `(repo_root, module_name)`, never by `module_name` alone, so two
  `repo_root`s with the same slug in one process never share a module
  (`D120`).
