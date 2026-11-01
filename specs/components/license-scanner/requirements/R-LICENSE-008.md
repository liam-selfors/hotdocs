# R-LICENSE-008

**R-LICENSE-008** — `gate_version(repo_root)` MUST return exactly the
  `gate_version` that `scan(component_id, repo_root)` would report, for
  any component, under the same `repo_root` and the same
  `VAR-LICENSE-CORPUS-PATH` value — including when the corpus is
  missing or unreadable. It MUST NOT scan any file under `gen/`, call
  `cache-manager`, or write anything. This is how a caller learns the
  scanner's current version without running a scan (`D163`).
