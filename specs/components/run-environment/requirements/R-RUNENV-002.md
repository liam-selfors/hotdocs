# R-RUNENV-002

**R-RUNENV-002** — `assets` MUST list, the `python` entry first with
  `path` `"."`, then one entry per declared asset in declaration order,
  `{"kind", "path", "definition_sha256", "adapter_sha256", "versions", "lockfile_sha256"}`
  as `specs/architecture/asset-kinds.md`'s Provenance bullet states. A
  kind with no adapter has `adapter_sha256` null, `versions` `{}` and
  `lockfile_sha256` null; a kind the repository does not define has
  `definition_sha256` null. Entries are listed for every declared asset,
  provisioned or not; a kind not reached has its adapter's hash,
  `versions` `{}` and `lockfile_sha256` null.
