# R-RUNENV-003

**R-RUNENV-003** — After the asset kinds, `prepare` MUST provision each
  declared test driver in sorted order, by
  `specs/architecture/test-drivers.md`'s Lookup, calling its
  `provision(repo_root)` once (`D373`). A driver with no adapter, or
  whose report has `ok` false, ends provisioning: `ok` is false and
  `failure_message` is `unknown test driver: <name>` or that report's
  `reason`. `drivers` lists one entry per declared driver, sorted, provisioned or
  not: one not provisioned has `versions` `{}` and `lockfile_sha256`
  null, one with no adapter `adapter_sha256` null,
  `{"name", "definition_sha256", "adapter_sha256", "versions", "lockfile_sha256"}`,
  the hashes of `<repo_root>/specs/architecture/test-driver-<name>.md`
  (null when absent) and of the adapter module found, each
  `"sha256:"` and the lowercase hex SHA-256 of the file's bytes.
