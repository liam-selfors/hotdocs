# R-SUPPLY-001

**R-SUPPLY-001** — `supply` MUST use the committed test, without
  calling `test_author`, exactly when it exists, is current by
  `specs/architecture/test-reuse.md`'s criterion header for the
  criterion's bundle, and passes its probe. The bundle is exactly what
  `spec-bundle-assembler`'s `assemble_criterion(component_id,
  criterion_id, repo_root)` returns, never one built here (`D119`); a
  header line is one matching `^# hotdocs-criterion: sha256:[0-9a-f]{64}$`.
