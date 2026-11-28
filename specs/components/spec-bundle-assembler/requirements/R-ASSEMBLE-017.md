# R-ASSEMBLE-017

**R-ASSEMBLE-017** — Test drivers (`D373`,
  `specs/architecture/test-drivers.md`). The target's declared drivers
  are the items of its `component.md` frontmatter `drivers` line, read
  as `R-ASSEMBLE-016` reads `assets`, sorted; none when absent. A
  driver's adapter is `<repo_root>/gen/driver-<name>/driver_<module>.py`,
  else the same path under the tool root, loaded by path afresh on each
  call; with neither, both functions raise `PreconditionFailure` with
  `unknown test driver: <name>`. `assemble_criterion` MUST append to
  `CriterionBundle.testing`, after the asset kinds' texts, for each,
  `"\n## Test driver: " + name + "\n\n" + guidance()["test_author"]`
  stripped. `SpecBundle` never holds it. Each adapter is hashed as an
  asset-kind adapter is (`R-ASSEMBLE-007`), under
  `gen/driver-<name>/driver_<module>.py`.
