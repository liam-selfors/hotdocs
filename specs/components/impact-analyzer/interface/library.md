# Library

```
compute_blast_radius(changed_ids: list[str], repo_root: Path) -> BlastRadiusReport
```

A pure function over the filesystem state at `repo_root` — no network
access, no model calls, no side effects. Raises/returns an explicit
precondition-failure result (not a best-effort partial one) if the corpus
graph isn't lint-clean.

So any corpus it is run on, a test's included, must lint clean under
`SPEC_GUIDELINES.md` and `spec-linter`: for example, each requirement
or guarantee file opens with the heading `# <its id>`, equal to its
filename's stem, and states itself with an RFC 2119 keyword.

Implements: `specs/architecture/cli-conventions.md`
