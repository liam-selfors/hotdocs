# R-AUTHOR-020

**R-AUTHOR-020** — `author_test` MUST validate every extracted test with
  `test-probe`'s `probe(content, bundle, module_name, drivers=drivers)`,
  `content` the extracted file as extracted, without `R-AUTHOR-028`'s
  header, `module_name` the bundle's `module_names` list when it is
  non-empty (`R-AUTHOR-026`), else the component's slug with hyphens
  replaced by underscores, and `drivers` the `<name>` of each line
  `## Test driver: <name>` in the bundle's `testing`, in order, `[]`
  when there is none (`D385`), never relying on the model's self-check
  alone and applying no other check before it. A test whose
  `ProbeReport` has `ok` false is rejected: it goes to the repair loop
  (`R-AUTHOR-027`) and is never written as it stands.
