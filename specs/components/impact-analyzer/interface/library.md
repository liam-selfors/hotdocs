# Library

```
compute_blast_radius(changed_ids: list[str], repo_root: Path) -> BlastRadiusReport
```

A pure function over the filesystem state at `repo_root` — no network
access, no model calls, no side effects. Raises/returns an explicit
precondition-failure result (not a best-effort partial one) if the corpus
graph isn't lint-clean.

Implements: `specs/architecture/cli-conventions.md`
